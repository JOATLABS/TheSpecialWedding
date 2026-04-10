#!/bin/bash

# Script to create GitHub releases for retroactive tags
# Requires GitHub CLI (gh) to be installed and authenticated

echo "📦 Creating GitHub Releases for Claude-Command-Suite"
echo "================================================"

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo "Run: gh auth login"
    exit 1
fi

# Function to create a release
create_release() {
    local tag=$1
    local title=$2
    local body=$3

    echo "Creating release for $tag..."

    # Create temporary file for release notes
    local temp_file=$(mktemp)
    echo "$body" > "$temp_file"

    # Create the release
    gh release create "$tag" \
        --title "$title" \
        --notes-file "$temp_file" \
        --target main

    # Clean up
    rm "$temp_file"

    echo "✅ Created release $tag"
    echo ""
}

# Create releases for each version

# v1.0.0
create_release "v1.0.0" "v1.0.0 - Initial Release" "## 🎉 Initial Release of Claude-Command-Suite

Originally released as 'claude-rules', this is the foundation of the Claude-Command-Suite.

### ✨ Features
- **25+ specialized slash commands** for Claude Code
- **Interactive installation script** with multiple installation methods
- **Command templates** for analysis, development, and maintenance workflows
- **Cross-platform support** for any programming language or framework

### 📦 Commands Included

**Analysis Commands:**
- \`architecture-review\` - Analyze system architecture
- \`code-review\` - Complete code quality review
- \`security-audit\` - Security vulnerability assessment
- \`performance-audit\` - Performance bottleneck identification
- \`dependency-audit\` - Dependency security scanning

**Development Commands:**
- \`create-feature\` - End-to-end feature development
- \`fix-issue\` - Structured issue resolution
- \`refactor-code\` - Safe refactoring workflow
- \`debug-error\` - Systematic debugging approach
- \`optimize-build\` - Build system improvements

### 🚀 Installation
\`\`\`bash
git clone https://github.com/qdhenry/Claude-Command-Suite.git
cd Claude-Command-Suite
./install.sh
\`\`\`"

# v1.0.1
create_release "v1.0.1" "v1.0.1 - Hotfix Release" "## 🐛 Bug Fix Release

### Fixed
- Fixed formatting and structure of \`hotfix-deploy.md\` command

This patch release ensures the hotfix deployment command works correctly."

# v1.1.0
create_release "v1.1.0" "v1.1.0 - Documentation Overhaul" "## 📚 Documentation Improvements

Major documentation restructuring for better user experience.

### ✨ Added
- **Beginner-friendly README** with simplified structure
- **Comprehensive guides:**
  - \`docs/INSTALLATION.md\` - Detailed setup methods
  - \`docs/CUSTOMIZATION.md\` - Command modification guide
  - \`docs/DEVELOPMENT.md\` - Testing and contribution guidelines
  - \`docs/ROADMAP.md\` - Future development plans
- **Contributing section** encouraging community participation

### 🔄 Changed
- Restructured documentation for better user experience
- Moved detailed content to dedicated guides
- Organized all docs into \`docs/\` directory
- Simplified command descriptions to one-line summaries"

# v1.2.0
create_release "v1.2.0" "v1.2.0 - Roadmap Implementation" "## 🚀 Major Feature Release

Implementation of 30+ commands from the project roadmap!

### ✨ Added Commands

**Project Setup:**
- \`init-project\` - Initialize new projects
- \`setup-monorepo\` - Configure monorepo structure
- \`add-package\` - Add new packages/modules

**Testing Suite:**
- \`setup-comprehensive-testing\` - Complete testing stack
- \`e2e-setup\` - End-to-end testing
- \`setup-visual-testing\` - Visual regression testing
- \`add-property-based-testing\` - Property testing framework

**DevOps & Infrastructure:**
- \`containerize-application\` - Docker configuration
- \`setup-kubernetes-deployment\` - K8s manifests
- \`setup-monitoring-observability\` - Monitoring stack

**Database & API:**
- \`design-database-schema\` - Schema design
- \`create-database-migrations\` - Safe migrations
- \`design-rest-api\` - RESTful API design
- \`implement-graphql-api\` - GraphQL implementation

And many more! Total commands: 55+"

# v1.3.0
create_release "v1.3.0" "v1.3.0 - CI/CD & Automation" "## 🤖 Automation Features

### ✨ Added
- **Automated changelog generation** system
- **GitHub Actions workflow** for PR reviews with Claude
- **CI/CD integration** for command validation
- **Bypass mechanism** for automated workflows

### 🐛 Fixed
- Installation directory name in documentation
- GitHub Actions workflow CI compatibility

### 🔧 Developer Experience
This release significantly improves the development workflow with automated PR reviews and changelog generation."

# v1.4.0
create_release "v1.4.0" "v1.4.0 - Project Management Suite" "## 📋 Project Management Commands

Massive addition of project management capabilities!

### ✨ Added
- **24 project management commands** including:

**Sprint Planning & Analysis:**
- \`sprint-planning\` - Sprint capacity planning
- \`standup-report\` - Daily standup generation
- \`project-health-check\` - Project metrics
- \`retrospective-analyzer\` - Sprint retrospectives
- \`milestone-tracker\` - Milestone tracking

**Task Management:**
- \`project-to-linear\` - Create Linear tasks
- \`task-from-pr\` - Convert PRs to tasks
- \`dependency-mapper\` - Task dependencies
- \`estimate-assistant\` - Task estimation
- \`team-workload-balancer\` - Workload optimization

**GitHub-Linear Sync:**
- \`bidirectional-sync\` - Two-way synchronization
- \`sync-pr-to-task\` - PR-task linking
- \`migration-assistant\` - Bulk migration tools

### 🎯 Improvements
- Added command count badge (81 total commands)
- Fixed missing Instructions sections
- Enhanced command validation

Total commands: 81"

# v1.5.0
create_release "v1.5.0" "v1.5.0 - Ultra Think & Memory Commands" "## 🧠 Advanced Reasoning and Memory Management

### ✨ Added

**Ultra Think Command:**
- \`ultra-think\` - Deep analytical reasoning mode for complex problem-solving

**Memory Management Commands** (contributed by Thomas Landgraf):
- \`analyze-memory-commands\` - Analyze memory patterns
- \`setup-memory-system\` - Configure memory system
- \`visualize-memory\` - Visualize memory usage

### 🐛 Fixed
- Command outputs properly quoted in changelog workflow

Total commands: 85"

# v1.6.0
create_release "v1.6.0" "v1.6.0 - Utility Commands" "## 🔧 Utility Commands Release

### ✨ Added

**4 Utility Commands** (contributed by IndyDevDan/DislerH from claude-code-hooks-mastery):
- \`all-tools\` - List all available tools in TypeScript function signature format
- \`git-status\` - Comprehensive git repository status analysis
- \`prime\` - Load essential context for new agent sessions
- \`sentient\` - Test Claude Code hook protections (demonstration command)

### 🐛 Fixed
- Syntax error in update-changelog.yml workflow

### 🙏 Credits
Special thanks to:
- **IndyDevDan** (YouTube: https://www.youtube.com/@indydevdan)
- **DislerH** (GitHub: https://github.com/disler)

Total commands: 89"

echo "✅ All releases created successfully!"
echo ""
echo "View releases at: https://github.com/qdhenry/Claude-Command-Suite/releases"
