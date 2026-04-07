"""
Database Backup API

Automated MongoDB backups triggered by Cloudflare Workers Cron (FREE).
Uploads to Cloudflare R2 (you already use this for gallery storage!).

Zero-cost backup solution:
- Cloudflare Workers Cron (FREE - unlimited scheduled workers)
- Cloudflare R2 storage (FREE - 10GB included)
- Automated retention policy (30 days)
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database import mongo
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["ROOT_ADMIN", "Backup"])

# Backup secret for Cloudflare Workers authentication
BACKUP_SECRET = os.getenv("BACKUP_SECRET")


@router.post("/trigger")
async def trigger_backup(
    authorization: str = Header(None, description="Bearer token for authentication"),
) -> Dict[str, Any]:
    """
    Trigger MongoDB backup and upload to R2

    This endpoint is called by Cloudflare Workers Cron.
    Requires BACKUP_SECRET in Authorization header.

    Flow:
    1. Cloudflare Worker Cron runs daily (2am UTC)
    2. Calls this endpoint with BACKUP_SECRET
    3. Creates mongodump
    4. Uploads to R2
    5. Cleans up old backups
    """

    # Verify secret token (not JWT - this is for Cloudflare Workers)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.split("Bearer ")[1].strip()

    if not BACKUP_SECRET:
        logger.error("BACKUP_SECRET not set in environment")
        raise HTTPException(status_code=500, detail="Backup system not configured")

    if token != BACKUP_SECRET:
        logger.warning("Invalid backup secret attempt")
        raise HTTPException(status_code=401, detail="Invalid backup secret")

    try:
        logger.info("Starting database backup...")

        # Create backup filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_filename = f"mongodb-backup-{timestamp}.gz"
        backup_path = f"/tmp/{backup_filename}"

        # Get MongoDB URI
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise Exception("MONGO_URI not set")

        # Run mongodump
        logger.info(f"Running mongodump to {backup_path}...")

        dump_command = [
            "mongodump",
            "--uri",
            mongo_uri,
            "--gzip",
            f"--archive={backup_path}",
        ]

        # Run subprocess asynchronously
        process = await asyncio.create_subprocess_exec(
            *dump_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode() if stderr else "Unknown error"
            logger.error(f"mongodump failed: {error_message}")
            raise Exception(f"Backup failed: {error_message}")

        logger.info("mongodump completed successfully")

        # Get file size
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Backup file size: {file_size_mb:.2f} MB")

        # Upload to R2 using boto3 (you already have S3 config for R2!)
        try:
            import boto3
            from botocore.config import Config

            # Create S3 client for R2
            s3_client = boto3.client(
                "s3",
                endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
                config=Config(signature_version="s3v4"),
            )

            bucket_name = os.getenv("S3_BUCKET_NAME")
            if not bucket_name:
                raise Exception("S3_BUCKET_NAME not set")

            # Upload file
            s3_key = f"backups/{backup_filename}"

            logger.info(f"Uploading to R2: {s3_key}...")

            with open(backup_path, "rb") as f:
                s3_client.upload_fileobj(
                    f,
                    bucket_name,
                    s3_key,
                    ExtraArgs={
                        "Metadata": {
                            "backup-date": timestamp,
                            "retention-days": "30",
                            "file-size-mb": str(file_size_mb),
                            "database": os.getenv("MONGO_DB", "wedding"),
                        }
                    },
                )

            logger.info("Upload to R2 completed successfully")

        except Exception as upload_error:
            logger.error(f"Failed to upload to R2: {str(upload_error)}")
            # Clean up local file
            if os.path.exists(backup_path):
                os.remove(backup_path)
            raise

        # Clean up local backup file
        if os.path.exists(backup_path):
            os.remove(backup_path)
            logger.info("Cleaned up local backup file")

        # Save backup record to database
        backup_record = {
            "backup_id": timestamp,
            "backup_date": datetime.now(timezone.utc),
            "filename": backup_filename,
            "file_size_bytes": file_size,
            "file_size_mb": file_size_mb,
            "storage_location": "R2",
            "storage_key": s3_key,
            "status": "success",
            "retention_days": 30,
        }

        await mongo.db["backup_history"].insert_one(backup_record)

        # Clean up old backups (retention policy)
        await cleanup_old_backups(days=30, s3_client=s3_client, bucket_name=bucket_name)

        return {
            "status": "success",
            "backup_date": datetime.now(timezone.utc).isoformat(),
            "filename": backup_filename,
            "file_size_mb": round(file_size_mb, 2),
            "storage_location": "R2",
            "storage_key": s3_key,
        }

    except Exception as e:
        logger.error(f"Backup failed: {str(e)}", exc_info=True)

        # Log failure to database
        try:
            await mongo.db["backup_history"].insert_one(
                {
                    "backup_date": datetime.now(timezone.utc),
                    "status": "failed",
                    "error": str(e),
                }
            )
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


async def cleanup_old_backups(days: int, s3_client, bucket_name: str):
    """
    Delete backups older than retention period

    Args:
        days: Retention period in days
        s3_client: Boto3 S3 client
        bucket_name: R2 bucket name
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(f"Cleaning up backups older than {cutoff_date.isoformat()}")

        # List all backups in R2
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="backups/")

        if "Contents" not in response:
            logger.info("No backups found to clean up")
            return

        deleted_count = 0

        for obj in response["Contents"]:
            # Get object metadata
            head = s3_client.head_object(Bucket=bucket_name, Key=obj["Key"])

            # Check backup date from metadata
            backup_date_str = head.get("Metadata", {}).get("backup-date")

            if backup_date_str:
                try:
                    backup_date = datetime.strptime(backup_date_str, "%Y%m%d-%H%M%S")

                    if backup_date < cutoff_date:
                        # Delete old backup
                        s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
                        logger.info(f"Deleted old backup: {obj['Key']}")
                        deleted_count += 1

                        # Update database record
                        await mongo.db["backup_history"].update_one(
                            {"storage_key": obj["Key"]},
                            {
                                "$set": {
                                    "deleted_at": datetime.now(timezone.utc),
                                    "status": "deleted",
                                }
                            },
                        )

                except Exception as e:
                    logger.error(f"Failed to process backup {obj['Key']}: {str(e)}")

        logger.info(f"Cleanup complete. Deleted {deleted_count} old backups")

    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {str(e)}")
        # Don't raise - cleanup failure shouldn't fail the backup


@router.get("/history")
async def get_backup_history(
    limit: int = 30, current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get backup history

    Shows all backups, their status, and file sizes.
    """
    cursor = mongo.db["backup_history"].find().sort("backup_date", -1).limit(limit)
    backups = await cursor.to_list(length=limit)

    # Convert ObjectId to string
    for backup in backups:
        if "_id" in backup:
            backup["_id"] = str(backup["_id"])

    # Calculate statistics
    successful = len([b for b in backups if b.get("status") == "success"])
    failed = len([b for b in backups if b.get("status") == "failed"])
    total_size_mb = sum(
        b.get("file_size_mb", 0) for b in backups if b.get("status") == "success"
    )

    return {
        "backups": backups,
        "statistics": {
            "total": len(backups),
            "successful": successful,
            "failed": failed,
            "total_size_mb": round(total_size_mb, 2),
        },
    }


@router.get("/latest")
async def get_latest_backup(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
) -> Dict[str, Any]:
    """Get information about the most recent backup"""

    backup = await mongo.db["backup_history"].find_one(
        {"status": "success"}, sort=[("backup_date", -1)]
    )

    if not backup:
        raise HTTPException(status_code=404, detail="No successful backups found")

    # Convert ObjectId to string
    if "_id" in backup:
        backup["_id"] = str(backup["_id"])

    # Calculate age
    age_hours = (
        datetime.now(timezone.utc) - backup["backup_date"]
    ).total_seconds() / 3600

    return {
        **backup,
        "age_hours": round(age_hours, 1),
        "is_fresh": age_hours
        < 26,  # Should be < 26 hours old (daily backups + 2h grace)
    }


@router.post("/restore-info/{backup_id}")
async def get_restore_info(
    backup_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get restore instructions for a specific backup

    Note: Actual restore requires manual intervention for safety.
    This provides the commands to run.
    """

    backup = await mongo.db["backup_history"].find_one(
        {"backup_id": backup_id, "status": "success"}
    )

    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Generate restore instructions
    instructions = f"""
# MongoDB Restore Instructions for Backup: {backup_id}

⚠️  WARNING: Restoring will overwrite your current database!

## Step 1: Download backup from R2

```bash
# Using AWS CLI (configure with R2 credentials)
aws s3 cp \\
  s3://{os.getenv("S3_BUCKET_NAME")}/{backup["storage_key"]} \\
  /tmp/{backup["filename"]} \\
  --endpoint-url {os.getenv("S3_ENDPOINT_URL")}
```

## Step 2: Restore MongoDB

```bash
# Stop your application first!
docker-compose down

# Restore the backup
mongorestore \\
  --uri "{os.getenv("MONGO_URI")}" \\
  --gzip \\
  --archive=/tmp/{backup["filename"]} \\
  --drop

# Restart your application
docker-compose up -d
```

## Backup Details

- Date: {backup["backup_date"].strftime("%Y-%m-%d %H:%M:%S UTC")}
- Size: {backup["file_size_mb"]:.2f} MB
- Location: R2 - {backup["storage_key"]}

## Important Notes

1. Always test restores on a staging environment first
2. Backup your current database before restoring
3. Verify data integrity after restore
4. Update any dependent services
    """

    return {
        "backup_id": backup_id,
        "backup_date": backup["backup_date"].isoformat(),
        "file_size_mb": backup["file_size_mb"],
        "instructions": instructions,
    }


@router.delete("/cleanup-old")
async def manual_cleanup_old_backups(
    days: int = 30, current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Manually trigger cleanup of old backups

    Args:
        days: Delete backups older than this many days
    """
    try:
        import boto3
        from botocore.config import Config

        s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise HTTPException(
                status_code=500,
                detail="S3_BUCKET_NAME environment variable not configured",
            )

        await cleanup_old_backups(days, s3_client, bucket_name)

        return {
            "status": "success",
            "message": f"Cleaned up backups older than {days} days",
        }

    except Exception as e:
        logger.error(f"Manual cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
