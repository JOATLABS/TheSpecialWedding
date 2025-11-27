#!/usr/bin/env python3
"""
Script to validate the Pydantic v2 migration.
Checks all updated models and provides migration status report.
"""
import sys
import os
import importlib
import traceback
from pathlib import Path
from typing import List, Dict, Any

# Add the app directory to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'app'))


class PydanticMigrationValidator:
    """Validates the Pydantic v2 migration status."""

    def __init__(self):
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': [],
            'summary': {}
        }

    def validate_imports(self) -> bool:
        """Test that all critical imports work."""
        print("🔍 Testing imports...")

        import_tests = [
            ('utils.pydantic_objectid', ['PyObjectId', 'generate_object_id', 'is_valid_object_id']),
            ('models.base', ['TimestampedModel', 'MongoModel', 'WeddingRelatedModel']),
            ('models.budget', ['BudgetCategory', 'VendorQuote', 'BudgetTemplate']),
            ('models.form', ['FormModel', 'FormField', 'FormSettings']),
            ('models.wedding', ['WeddingModel', 'EventModel']),
            ('models.subscription', ['SubscriptionPlanModel', 'UserSubscriptionModel']),
            ('core.settings', ['Settings'])
        ]

        all_passed = True

        for module_name, classes in import_tests:
            try:
                module = importlib.import_module(module_name)
                for class_name in classes:
                    if not hasattr(module, class_name):
                        self.results['failed'].append(f"❌ {module_name}.{class_name} not found")
                        all_passed = False
                    else:
                        self.results['passed'].append(f"✅ {module_name}.{class_name}")
            except ImportError as e:
                self.results['failed'].append(f"❌ Import error for {module_name}: {e}")
                all_passed = False
            except Exception as e:
                self.results['failed'].append(f"❌ Unexpected error importing {module_name}: {e}")
                all_passed = False

        return all_passed

    def validate_objectid_functionality(self) -> bool:
        """Test ObjectId functionality."""
        print("🔧 Testing ObjectId functionality...")

        try:
            from utils.pydantic_objectid import PyObjectId, generate_object_id, is_valid_object_id

            # Test generation
            test_id = generate_object_id()
            if not test_id:
                self.results['failed'].append("❌ ObjectId generation failed")
                return False

            # Test validation
            if not is_valid_object_id(str(test_id)):
                self.results['failed'].append("❌ ObjectId validation failed")
                return False

            # Test string conversion
            str_id = str(test_id)
            if len(str_id) != 24:
                self.results['failed'].append(f"❌ ObjectId string length wrong: {len(str_id)}")
                return False

            self.results['passed'].append("✅ ObjectId functionality working")
            return True

        except Exception as e:
            self.results['failed'].append(f"❌ ObjectId test failed: {e}")
            return False

    def validate_model_configs(self) -> bool:
        """Check that models use model_config instead of Config class."""
        print("⚙️ Validating model configurations...")

        models_to_check = [
            ('models.budget', 'BudgetCategory'),
            ('models.budget', 'VendorQuote'),
            ('models.budget', 'BudgetTemplate'),
            ('models.form', 'FormModel'),
            ('models.wedding', 'WeddingModel'),
            ('models.subscription', 'SubscriptionPlanModel'),
        ]

        all_passed = True

        for module_name, class_name in models_to_check:
            try:
                module = importlib.import_module(module_name)
                model_class = getattr(module, class_name)

                # Check for model_config
                if not hasattr(model_class, 'model_config'):
                    self.results['failed'].append(f"❌ {class_name} missing model_config")
                    all_passed = False
                    continue

                # Check for old Config class
                if hasattr(model_class, 'Config'):
                    self.results['warnings'].append(f"⚠️ {class_name} still has old Config class")

                # Check model_config properties
                config = model_class.model_config
                if not isinstance(config, dict):
                    self.results['warnings'].append(f"⚠️ {class_name} model_config is not a dict")

                self.results['passed'].append(f"✅ {class_name} model_config validated")

            except Exception as e:
                self.results['failed'].append(f"❌ Error checking {class_name}: {e}")
                all_passed = False

        return all_passed

    def validate_model_creation(self) -> bool:
        """Test that models can be created with valid data."""
        print("🏗️ Testing model creation...")

        test_cases = [
            {
                'module': 'models.budget',
                'class': 'BudgetCategory',
                'data': {
                    'wedding_id': '507f1f77bcf86cd799439011',
                    'name': 'Test Category',
                    'budgeted_amount': 1000.0
                }
            },
            {
                'module': 'models.budget',
                'class': 'VendorQuote',
                'data': {
                    'wedding_id': '507f1f77bcf86cd799439012',
                    'vendor_name': 'Test Vendor',
                    'service_category': 'photography',
                    'quote_amount': 2500.0
                }
            },
            {
                'module': 'models.form',
                'class': 'FormField',
                'data': {
                    'id': 'test_field',
                    'label': 'Test Field',
                    'type': 'text'
                }
            }
        ]

        all_passed = True

        for test_case in test_cases:
            try:
                module = importlib.import_module(test_case['module'])
                model_class = getattr(module, test_case['class'])

                # Create instance
                instance = model_class(**test_case['data'])

                # Test basic properties
                if not instance:
                    self.results['failed'].append(f"❌ {test_case['class']} creation failed")
                    all_passed = False
                    continue

                # Test serialization
                try:
                    json_str = instance.model_dump_json()
                    if not json_str:
                        self.results['warnings'].append(f"⚠️ {test_case['class']} JSON serialization empty")
                except Exception as e:
                    self.results['warnings'].append(f"⚠️ {test_case['class']} serialization issue: {e}")

                self.results['passed'].append(f"✅ {test_case['class']} creation successful")

            except Exception as e:
                self.results['failed'].append(f"❌ {test_case['class']} creation failed: {e}")
                all_passed = False

        return all_passed

    def validate_schema_generation(self) -> bool:
        """Test JSON schema generation."""
        print("📋 Testing schema generation...")

        models_to_test = [
            ('models.budget', 'BudgetCategory'),
            ('models.form', 'FormModel'),
        ]

        all_passed = True

        for module_name, class_name in models_to_test:
            try:
                module = importlib.import_module(module_name)
                model_class = getattr(module, class_name)

                # Generate schema
                schema = model_class.model_json_schema()

                # Basic schema validation
                if not isinstance(schema, dict):
                    self.results['failed'].append(f"❌ {class_name} schema not a dict")
                    all_passed = False
                    continue

                if 'properties' not in schema:
                    self.results['failed'].append(f"❌ {class_name} schema missing properties")
                    all_passed = False
                    continue

                self.results['passed'].append(f"✅ {class_name} schema generation working")

            except Exception as e:
                self.results['failed'].append(f"❌ {class_name} schema generation failed: {e}")
                all_passed = False

        return all_passed

    def check_pydantic_version(self) -> bool:
        """Check Pydantic version compatibility."""
        print("📦 Checking Pydantic version...")

        try:
            import pydantic
            version = pydantic.__version__

            major_version = int(version.split('.')[0])
            if major_version < 2:
                self.results['failed'].append(f"❌ Pydantic version {version} is < 2.0")
                return False

            self.results['passed'].append(f"✅ Pydantic version {version} is compatible")
            return True

        except Exception as e:
            self.results['failed'].append(f"❌ Could not check Pydantic version: {e}")
            return False

    def generate_report(self) -> str:
        """Generate a comprehensive migration report."""
        passed_count = len(self.results['passed'])
        failed_count = len(self.results['failed'])
        warning_count = len(self.results['warnings'])
        total_tests = passed_count + failed_count

        success_rate = (passed_count / total_tests * 100) if total_tests > 0 else 0

        report = f"""
🚀 PYDANTIC V2 MIGRATION VALIDATION REPORT
{'=' * 50}

📊 SUMMARY:
✅ Passed: {passed_count}
❌ Failed: {failed_count}
⚠️  Warnings: {warning_count}
📈 Success Rate: {success_rate:.1f}%

"""

        if self.results['passed']:
            report += "\n✅ PASSED TESTS:\n"
            for item in self.results['passed'][:10]:  # Show first 10
                report += f"   {item}\n"
            if len(self.results['passed']) > 10:
                report += f"   ... and {len(self.results['passed']) - 10} more\n"

        if self.results['failed']:
            report += "\n❌ FAILED TESTS:\n"
            for item in self.results['failed']:
                report += f"   {item}\n"

        if self.results['warnings']:
            report += "\n⚠️  WARNINGS:\n"
            for item in self.results['warnings']:
                report += f"   {item}\n"

        # Status assessment
        if failed_count == 0:
            report += "\n🎉 MIGRATION STATUS: COMPLETE ✅"
            report += "\nAll tests passed! Your Pydantic v2 migration is successful."
        elif failed_count <= 2:
            report += "\n⚠️  MIGRATION STATUS: MOSTLY COMPLETE"
            report += "\nMost tests passed, but there are a few issues to address."
        else:
            report += "\n🚨 MIGRATION STATUS: NEEDS WORK"
            report += "\nSeveral issues need to be resolved before migration is complete."

        return report

    def run_all_validations(self) -> bool:
        """Run all validation tests."""
        print("🚀 Starting Pydantic v2 Migration Validation")
        print("=" * 50)

        tests = [
            self.check_pydantic_version,
            self.validate_imports,
            self.validate_objectid_functionality,
            self.validate_model_configs,
            self.validate_model_creation,
            self.validate_schema_generation,
        ]

        all_passed = True

        for test in tests:
            try:
                if not test():
                    all_passed = False
            except Exception as e:
                self.results['failed'].append(f"❌ Test {test.__name__} crashed: {e}")
                all_passed = False
            print("-" * 30)

        return all_passed


def main():
    """Run the validation and generate report."""
    validator = PydanticMigrationValidator()

    try:
        success = validator.run_all_validations()
        report = validator.generate_report()

        print(report)

        # Save report to file
        report_path = project_root / 'tests' / 'results' / 'pydantic_v2_migration_report.md'
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            f.write(report)

        print(f"\n📄 Full report saved to: {report_path}")

        return success

    except Exception as e:
        print(f"❌ Validation crashed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)