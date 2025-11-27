#!/bin/bash

# Automation Attributes Detection Script
# Identifies components and elements that may need automation attributes

echo "=========================================="
echo "🔍 Automation Attributes Detection Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="/home/emmanuel/Desktop/WeddingApp/WeddingWebApp"
APP_DIR="$PROJECT_ROOT/app"

echo -e "${BLUE}📊 Scanning project for automation coverage...${NC}"
echo ""

# Function to count interactive elements in a file
count_interactive_elements() {
    local file="$1"
    local buttons=$(grep -c -E '<button|<Button' "$file" 2>/dev/null || echo 0)
    local inputs=$(grep -c -E '<input|<Input' "$file" 2>/dev/null || echo 0)
    local selects=$(grep -c -E '<select|<Select' "$file" 2>/dev/null || echo 0)
    local forms=$(grep -c -E '<form|<Form' "$file" 2>/dev/null || echo 0)
    local links=$(grep -c -E '<Link|<a' "$file" 2>/dev/null || echo 0)
    echo $((buttons + inputs + selects + forms + links))
}

# Function to count automation attributes in a file
count_automation_attrs() {
    local file="$1"
    local data_testid=$(grep -c 'data-testid=' "$file" 2>/dev/null || echo 0)
    local automation_attrs=$(grep -c -E 'guestAutomationAttrs|formAutomationAttrs|authAutomationAttrs|createAutomationAttrs' "$file" 2>/dev/null || echo 0)
    echo $((data_testid + automation_attrs))
}

# Statistics
total_files=0
enhanced_files=0
total_elements=0
attributed_elements=0
missing_attributes_files=()

echo -e "${YELLOW}📁 Analyzing TSX/JSX files...${NC}"
echo ""

# Scan all TSX and JSX files in app directory
while IFS= read -r -d '' file; do
    if [[ -f "$file" ]]; then
        total_files=$((total_files + 1))

        # Get relative path for display
        rel_path=${file#$PROJECT_ROOT/}

        # Count elements and attributes
        elements=$(count_interactive_elements "$file")
        attrs=$(count_automation_attrs "$file")

        total_elements=$((total_elements + elements))
        attributed_elements=$((attributed_elements + attrs))

        if [[ $elements -gt 0 ]]; then
            coverage_ratio=0
            if [[ $attrs -gt 0 ]]; then
                coverage_ratio=$(echo "scale=1; $attrs * 100 / $elements" | bc -l 2>/dev/null || echo "0")
                enhanced_files=$((enhanced_files + 1))
            fi

            # Determine status
            if [[ $attrs -eq 0 ]]; then
                status="${RED}❌ No automation${NC}"
                missing_attributes_files+=("$rel_path")
            elif (( $(echo "$coverage_ratio < 50" | bc -l 2>/dev/null || echo 1) )); then
                status="${YELLOW}⚠️  Partial (${coverage_ratio}%)${NC}"
            else
                status="${GREEN}✅ Good (${coverage_ratio}%)${NC}"
            fi

            printf "%-60s %2d elements | %s\n" "$rel_path" "$elements" "$status"
        fi
    fi
done < <(find "$APP_DIR" -name "*.tsx" -o -name "*.jsx" -print0)

echo ""
echo -e "${BLUE}📊 Summary Statistics${NC}"
echo "===================="
echo "Total TSX/JSX files analyzed: $total_files"
echo "Files with interactive elements: $(echo "${missing_attributes_files[@]}" | wc -w)"
echo "Files with automation attributes: $enhanced_files"
echo "Total interactive elements found: $total_elements"
echo "Elements with automation attributes: $attributed_elements"

if [[ $total_elements -gt 0 ]]; then
    overall_coverage=$(echo "scale=1; $attributed_elements * 100 / $total_elements" | bc -l 2>/dev/null || echo "0")
    echo "Overall coverage: ${overall_coverage}%"
fi

echo ""
echo -e "${YELLOW}🎯 Priority Files for Enhancement${NC}"
echo "=================================="

# Find files with high element counts but low/no automation
echo "Files with 5+ interactive elements needing automation:"
while IFS= read -r -d '' file; do
    if [[ -f "$file" ]]; then
        elements=$(count_interactive_elements "$file")
        attrs=$(count_automation_attrs "$file")

        if [[ $elements -ge 5 && $attrs -eq 0 ]]; then
            rel_path=${file#$PROJECT_ROOT/}
            echo "  📄 $rel_path ($elements elements)"
        fi
    fi
done < <(find "$APP_DIR" -name "*.tsx" -o -name "*.jsx" -print0)

echo ""
echo -e "${GREEN}🔧 Implementation Progress${NC}"
echo "=========================="
echo "✅ Authentication flow - Complete"
echo "✅ Guest management (RSVP, Admin) - Complete"
echo "⏳ Form builder system - Pending"
echo "⏳ UI component library - Pending"
echo "⏳ Admin dashboard - Pending"
echo "⏳ Wedding management - Pending"

echo ""
echo -e "${BLUE}🚀 Next Steps${NC}"
echo "=============="
echo "1. Focus on high-priority files with 5+ elements"
echo "2. Implement form builder automation attributes"
echo "3. Enhance UI component library base components"
echo "4. Add automation to admin dashboard components"
echo "5. Create comprehensive test suites using new attributes"

echo ""
echo -e "${YELLOW}💡 Usage Examples${NC}"
echo "=================="
echo "# Test specific enhanced components:"
echo "await page.click('[data-guest-id=\"123\"][data-action=\"edit\"]');"
echo "await page.fill('[data-field-id=\"name\"][data-field-required=\"true\"]', 'New Name');"
echo "await page.click('[data-action=\"save\"][data-form-valid=\"true\"]');"
echo ""
echo "# Test authentication flow:"
echo "await page.fill('[data-action=\"input-email\"]', 'user@example.com');"
echo "await page.click('[data-action=\"login\"][data-state=\"ready\"]');"
echo "await page.waitForSelector('[data-auth-state=\"authenticated\"]');"

echo ""
echo -e "${GREEN}✨ Detection complete!${NC}"
echo "=========================================="