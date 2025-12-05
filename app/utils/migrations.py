"""
Async Database Migration System

Zero-cost migration management using MongoDB and async/await.
Tracks applied migrations and provides rollback capability.

Usage:
    from app.utils.migrations import MigrationManager, migration_registry

    # Run all pending migrations
    await migration_manager.run_migrations()
"""

from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
import logging
from app.core.database import mongo

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration"""

    def __init__(
        self,
        version: str,
        name: str,
        up_func: Callable,
        down_func: Optional[Callable] = None,
        description: str = ""
    ):
        self.version = version
        self.name = name
        self.up = up_func
        self.down = down_func
        self.description = description

    def __repr__(self):
        return f"Migration({self.version}, {self.name})"


class MigrationManager:
    """
    Manages database migrations with async support
    """

    def __init__(self):
        self.migrations_collection_name = "_migrations"

    async def run_migrations(self, migrations: List[Migration]):
        """
        Run all pending migrations in order

        Args:
            migrations: List of Migration objects to run
        """
        if not migrations:
            logger.info("No migrations to run")
            return

        logger.info(f"Checking {len(migrations)} migrations...")

        for migration in migrations:
            if not await self._is_applied(migration.version):
                logger.info(f"⏳ Running migration: {migration.version} - {migration.name}")

                try:
                    # Run migration
                    await migration.up(mongo.db)

                    # Mark as applied
                    await mongo.db[self.migrations_collection_name].insert_one({
                        "version": migration.version,
                        "name": migration.name,
                        "description": migration.description,
                        "applied_at": datetime.utcnow(),
                        "status": "success"
                    })

                    logger.info(f"✓ Migration {migration.version} completed successfully")

                except Exception as e:
                    logger.error(f"✗ Migration {migration.version} failed: {str(e)}")

                    # Log failed migration
                    await mongo.db[self.migrations_collection_name].insert_one({
                        "version": migration.version,
                        "name": migration.name,
                        "description": migration.description,
                        "applied_at": datetime.utcnow(),
                        "status": "failed",
                        "error": str(e)
                    })

                    raise Exception(f"Migration {migration.version} failed: {str(e)}")
            else:
                logger.debug(f"⊘ Migration {migration.version} already applied, skipping")

    async def rollback_migration(self, version: str):
        """
        Rollback a specific migration

        Args:
            version: Version of migration to rollback
        """
        # Find the migration in registry
        migration = migration_registry.get_migration(version)

        if not migration:
            raise ValueError(f"Migration {version} not found in registry")

        if not migration.down:
            raise ValueError(f"Migration {version} has no rollback function")

        if not await self._is_applied(version):
            logger.warning(f"Migration {version} is not applied, cannot rollback")
            return

        logger.info(f"⏳ Rolling back migration: {version} - {migration.name}")

        try:
            # Run rollback
            await migration.down(mongo.db)

            # Remove from applied migrations
            await mongo.db[self.migrations_collection_name].delete_one({
                "version": version
            })

            logger.info(f"✓ Migration {version} rolled back successfully")

        except Exception as e:
            logger.error(f"✗ Rollback of {version} failed: {str(e)}")
            raise

    async def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of all applied migrations"""
        cursor = mongo.db[self.migrations_collection_name].find().sort("applied_at", 1)
        return await cursor.to_list(length=None)

    async def get_pending_migrations(self, all_migrations: List[Migration]) -> List[Migration]:
        """Get list of pending migrations"""
        pending = []
        for migration in all_migrations:
            if not await self._is_applied(migration.version):
                pending.append(migration)
        return pending

    async def _is_applied(self, version: str) -> bool:
        """Check if a migration has been applied"""
        result = await mongo.db[self.migrations_collection_name].find_one({
            "version": version,
            "status": "success"
        })
        return result is not None


class MigrationRegistry:
    """Registry to store and manage migrations"""

    def __init__(self):
        self.migrations: Dict[str, Migration] = {}
        self._ordered_migrations: List[Migration] = []

    def register(
        self,
        version: str,
        name: str,
        description: str = ""
    ):
        """
        Decorator to register a migration

        Usage:
            @migration_registry.register("001", "Add user fields", "Adds subscription fields to users")
            async def migration_001(db):
                await db["users"].update_many(
                    {},
                    {"$set": {"subscription_tier": "free"}}
                )
        """
        def decorator(up_func: Callable):
            # Look for corresponding down function
            down_func_name = f"rollback_{up_func.__name__}"
            down_func = None

            migration = Migration(
                version=version,
                name=name,
                up_func=up_func,
                down_func=down_func,
                description=description
            )

            self.migrations[version] = migration
            self._ordered_migrations.append(migration)
            self._ordered_migrations.sort(key=lambda m: m.version)

            logger.debug(f"Registered migration: {version} - {name}")

            return up_func

        return decorator

    def register_with_rollback(
        self,
        version: str,
        name: str,
        description: str = ""
    ):
        """
        Decorator to register a migration with rollback function

        Usage:
            @migration_registry.register_with_rollback("001", "Add user fields")
            class Migration001:
                async def up(db):
                    await db["users"].update_many({}, {"$set": {"field": "value"}})

                async def down(db):
                    await db["users"].update_many({}, {"$unset": {"field": ""}})
        """
        def decorator(migration_class):
            up_func = getattr(migration_class, 'up', None)
            down_func = getattr(migration_class, 'down', None)

            if not up_func:
                raise ValueError(f"Migration class must have 'up' method")

            migration = Migration(
                version=version,
                name=name,
                up_func=up_func,
                down_func=down_func,
                description=description
            )

            self.migrations[version] = migration
            self._ordered_migrations.append(migration)
            self._ordered_migrations.sort(key=lambda m: m.version)

            logger.debug(f"Registered migration with rollback: {version} - {name}")

            return migration_class

        return decorator

    def get_all_migrations(self) -> List[Migration]:
        """Get all migrations in order"""
        return self._ordered_migrations.copy()

    def get_migration(self, version: str) -> Optional[Migration]:
        """Get a specific migration by version"""
        return self.migrations.get(version)


# Global registry instance
migration_registry = MigrationRegistry()
migration_manager = MigrationManager()


# ==================== EXAMPLE MIGRATIONS ====================

@migration_registry.register(
    "001",
    "Initialize error tracking collection",
    "Creates the errors collection with indexes for fast querying"
)
async def migration_001_init_errors(db):
    """Initialize errors collection for self-hosted error tracking"""

    # Create indexes for errors collection
    await db["errors"].create_index("error_id", unique=True)
    await db["errors"].create_index("timestamp")
    await db["errors"].create_index("error_type")
    await db["errors"].create_index("acknowledged")
    await db["errors"].create_index([("timestamp", -1), ("acknowledged", 1)])

    logger.info("Created indexes for errors collection")


@migration_registry.register(
    "002",
    "Add platform metrics collection",
    "Creates collection for storing platform metrics snapshots"
)
async def migration_002_platform_metrics(db):
    """Create platform_metrics collection for historical tracking"""

    # Create time-series optimized indexes
    await db["platform_metrics"].create_index("timestamp")
    await db["platform_metrics"].create_index([("timestamp", -1)])

    logger.info("Created platform_metrics collection")


@migration_registry.register_with_rollback(
    "003",
    "Add subscription status to users",
    "Ensures all users have subscription_status and subscription_tier fields"
)
class Migration003:
    """Add subscription fields to existing users"""

    @staticmethod
    async def up(db):
        # Update users without subscription fields
        result = await db["users"].update_many(
            {"subscription_status": {"$exists": False}},
            {
                "$set": {
                    "subscription_status": "inactive",
                    "subscription_tier": "free",
                    "trial_used": False
                }
            }
        )
        logger.info(f"Updated {result.modified_count} users with subscription fields")

    @staticmethod
    async def down(db):
        # Rollback - remove subscription fields
        result = await db["users"].update_many(
            {},
            {
                "$unset": {
                    "subscription_status": "",
                    "subscription_tier": "",
                    "trial_used": ""
                }
            }
        )
        logger.info(f"Removed subscription fields from {result.modified_count} users")


@migration_registry.register(
    "004",
    "Add backup metadata collection",
    "Creates collection for tracking backup status and history"
)
async def migration_004_backup_tracking(db):
    """Create backup tracking collection"""

    await db["backup_history"].create_index("backup_date")
    await db["backup_history"].create_index([("backup_date", -1)])
    await db["backup_history"].create_index("status")

    logger.info("Created backup_history collection")


@migration_registry.register(
    "005",
    "Add production indexes for users collection",
    "Creates critical indexes for user queries, authentication, and subscription management"
)
async def migration_005_users_indexes(db):
    """Add production-critical indexes to users collection for performance"""

    # Email index - CRITICAL for authentication (unique constraint)
    await db["users"].create_index("email", unique=True)
    logger.info("Created unique index on users.email")

    # Role and status compound index - for listing users by type
    await db["users"].create_index([("role", 1), ("is_active", 1)])
    logger.info("Created compound index on users.(role, is_active)")

    # Subscription status index - for subscription management queries
    await db["users"].create_index("subscription_status")
    logger.info("Created index on users.subscription_status")

    # Trial end date index - for trial expiration checks
    await db["users"].create_index("trial_end_date")
    logger.info("Created index on users.trial_end_date")

    # Stripe customer ID index - for webhook processing
    await db["users"].create_index("stripe_customer_id", sparse=True)
    logger.info("Created sparse index on users.stripe_customer_id")

    # Created at index - for analytics and reporting
    await db["users"].create_index([("created_at", -1)])
    logger.info("Created descending index on users.created_at")

    # Compound index for trial expiration queries
    await db["users"].create_index([
        ("subscription_status", 1),
        ("trial_end_date", 1),
        ("is_active", 1)
    ])
    logger.info("Created compound index for trial expiration queries")

    logger.info("All users collection indexes created successfully")
