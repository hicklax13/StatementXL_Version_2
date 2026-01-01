# StatementXL User Guide

**Welcome to StatementXL!**  
Transform your financial PDFs into structured Excel templates with AI-powered extraction.

**Version:** 1.0.0  
**Last Updated:** December 31, 2025

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Uploading Documents](#uploading-documents)
3. [Reviewing Extracted Data](#reviewing-extracted-data)
4. [Creating Mappings](#creating-mappings)
5. [Exporting to Excel](#exporting-to-excel)
6. [Managing Your Account](#managing-your-account)
7. [Tips & Best Practices](#tips--best-practices)
8. [FAQ](#faq)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Creating Your Account

1. Visit [https://statementxl.com](https://statementxl.com)
2. Click **"Sign Up"**
3. Enter your email and create a password
4. Verify your email address
5. Complete your profile

### First Login

1. Go to [https://statementxl.com/login](https://statementxl.com/login)
2. Enter your email and password
3. Click **"Sign In"**

### Dashboard Overview

After logging in, you'll see your dashboard with:

- **Recent Documents:** Your uploaded PDFs
- **Quick Actions:** Upload, Create Template, View Exports
- **Usage Stats:** Documents processed this month
- **Notifications:** Important updates and alerts

---

## Uploading Documents

### Supported File Types

- **PDF** (Portable Document Format)
- Maximum file size: **50MB**
- Supported statement types:
  - Income Statements
  - Balance Sheets
  - Cash Flow Statements

### How to Upload

**Method 1: Drag & Drop**

1. Navigate to the **Upload** page
2. Drag your PDF file into the upload area
3. Wait for the upload to complete
4. Processing begins automatically

**Method 2: File Browser**

1. Click **"Choose File"** button
2. Select your PDF from your computer
3. Click **"Open"**
4. Click **"Upload"** to start processing

### Upload Limits

- **Free Plan:** 10 documents per month
- **Pro Plan:** 100 documents per month
- **Enterprise Plan:** Unlimited documents

### Processing Time

- **Simple PDFs:** 30-60 seconds
- **Complex PDFs:** 2-5 minutes
- **Scanned PDFs:** 3-10 minutes

You'll receive a notification when processing is complete.

---

## Reviewing Extracted Data

### Understanding the Extraction Results

After processing, you'll see:

**1. Document Summary**

- Statement type detected
- Number of tables found
- Processing confidence score

**2. Extracted Tables**

- Each table shown separately
- Row and column structure preserved
- Numbers automatically parsed

**3. Line Item Classification**

- AI-powered GAAP category assignment
- Confidence scores for each classification
- Suggested mappings

### Verifying Extracted Data

**Check for Accuracy:**

- ✅ All numbers extracted correctly
- ✅ Line item names match source
- ✅ Table structure preserved
- ✅ No missing rows or columns

**Common Issues:**

- ❌ Merged cells may split
- ❌ Footnotes might be included
- ❌ Headers may need adjustment

**How to Fix:**

1. Click **"Edit"** on any table
2. Correct any errors
3. Click **"Save Changes"**
4. Re-run classification if needed

---

## Creating Mappings

### What is a Mapping?

A mapping connects your extracted data to an Excel template, determining where each line item appears in the final file.

### Choosing a Template

1. Click **"Select Template"**
2. Browse available templates:
   - **Basic:** Simple formatting
   - **Corporate:** Professional styling
   - **Professional:** Advanced formulas
3. Preview the template
4. Click **"Use This Template"**

### Auto-Mapping

StatementXL automatically suggests mappings based on:

- GAAP category classification
- Line item names
- Historical patterns

**Review Auto-Mappings:**

1. Green checkmarks = High confidence
2. Yellow warnings = Medium confidence
3. Red alerts = Conflicts or issues

### Manual Mapping

**To manually map a line item:**

1. Click on the line item
2. Select the target cell in the template
3. Choose aggregation method (if multiple items):
   - **Sum:** Add values together
   - **Average:** Calculate average
   - **First:** Use first value only
4. Click **"Apply Mapping"**

### Resolving Conflicts

**Conflict Types:**

- **Duplicate Mapping:** Multiple items to same cell
- **Missing Category:** No matching GAAP category
- **Value Mismatch:** Numbers don't match expected format

**How to Resolve:**

1. Click on the conflict indicator
2. Review suggested resolutions
3. Choose the best option:
   - Merge items
   - Split into separate cells
   - Skip item
4. Click **"Resolve"**

---

## Exporting to Excel

### Generating Your Excel File

1. Review all mappings
2. Resolve any conflicts
3. Click **"Export to Excel"**
4. Choose export options:
   - **Include Formulas:** ✅ Recommended
   - **Include Formatting:** ✅ Recommended
   - **Include Notes:** Optional
5. Click **"Generate File"**

### Export Options

**Template Styles:**

- **Basic:** Simple black and white
- **Corporate:** Professional blue theme
- **Professional:** Premium green theme

**Formula Options:**

- **Working Formulas:** Cells contain actual formulas
- **Static Values:** Formulas converted to values
- **Both:** Separate sheets for each

### Downloading Your File

1. Wait for generation (usually 5-15 seconds)
2. Click **"Download"** when ready
3. File saves to your Downloads folder
4. File name format: `statement_YYYY-MM-DD.xlsx`

### What's Included

Your Excel file contains:

- ✅ All mapped line items
- ✅ Working formulas (if selected)
- ✅ Professional formatting
- ✅ Calculation totals
- ✅ Source reference notes

---

## Managing Your Account

### Profile Settings

**Update Your Information:**

1. Click your profile icon
2. Select **"Settings"**
3. Update:
   - Full name
   - Email address
   - Password
   - Notification preferences
4. Click **"Save Changes"**

### Subscription Management

**View Your Plan:**

- Navigate to **"Billing"**
- See current plan and usage
- View billing history

**Upgrade Your Plan:**

1. Click **"Upgrade"**
2. Choose new plan
3. Enter payment information
4. Confirm upgrade

**Cancel Subscription:**

1. Go to **"Billing"**
2. Click **"Cancel Subscription"**
3. Confirm cancellation
4. Access continues until period end

### Notification Preferences

**Email Notifications:**

- ✅ Processing complete
- ✅ Export ready
- ✅ Payment confirmations
- ⬜ Marketing emails (optional)

**In-App Notifications:**

- ✅ Document status updates
- ✅ Conflict alerts
- ✅ System announcements

---

## Tips & Best Practices

### For Best Results

**1. PDF Quality**

- Use high-resolution PDFs (300 DPI+)
- Avoid scanned images when possible
- Ensure text is selectable

**2. Document Preparation**

- Remove unnecessary pages
- Ensure tables are clearly formatted
- Check for merged cells

**3. Template Selection**

- Match template to statement type
- Consider your audience (internal vs. external)
- Preview before committing

**4. Mapping Review**

- Always review auto-mappings
- Verify totals match source
- Check formula references

**5. Export Verification**

- Open Excel file immediately
- Verify formulas calculate correctly
- Check formatting appears as expected

### Time-Saving Tips

**Keyboard Shortcuts:**

- `Ctrl+U` - Upload new document
- `Ctrl+E` - Export current mapping
- `Ctrl+S` - Save changes
- `Esc` - Cancel current action

**Batch Processing:**

1. Upload multiple PDFs at once
2. Process in background
3. Review all at once
4. Export in bulk

**Template Favorites:**

- Star frequently used templates
- Access from Quick Actions
- Faster template selection

---

## FAQ

### General Questions

**Q: What file types are supported?**  
A: Currently, only PDF files are supported. We're working on adding Excel and CSV support.

**Q: How long does processing take?**  
A: Most documents process in 30-60 seconds. Complex or scanned PDFs may take up to 10 minutes.

**Q: Can I edit the extracted data?**  
A: Yes! Click "Edit" on any table to make corrections before mapping.

**Q: Are my documents secure?**  
A: Absolutely. All uploads are encrypted, and we never share your data. See our [Privacy Policy](https://statementxl.com/privacy).

### Account & Billing

**Q: Can I try before I buy?**  
A: Yes! The Free plan includes 10 documents per month with no credit card required.

**Q: How do I upgrade my plan?**  
A: Go to Settings → Billing → Upgrade Plan. Changes take effect immediately.

**Q: Can I cancel anytime?**  
A: Yes, cancel anytime. You'll retain access until the end of your billing period.

**Q: Do you offer refunds?**  
A: We offer a 30-day money-back guarantee for annual plans.

### Technical Questions

**Q: Why isn't my PDF processing?**  
A: Check that:

- File is under 50MB
- File is a valid PDF
- PDF contains tables (not just text)
- You haven't exceeded your monthly limit

**Q: The extracted numbers are wrong. What do I do?**  
A: Click "Edit" on the table and correct the values manually. If the issue persists, contact support.

**Q: Can I use my own Excel templates?**  
A: Not yet, but custom templates are coming in Q1 2026!

**Q: Do the formulas work in Excel?**  
A: Yes! All formulas are native Excel formulas that work in Excel 2016+.

---

## Troubleshooting

### Upload Issues

**Problem: Upload fails**

- Check file size (max 50MB)
- Verify file is PDF format
- Check internet connection
- Try a different browser

**Problem: Processing stuck**

- Wait 10 minutes
- Refresh the page
- Contact support if still stuck

### Extraction Issues

**Problem: No tables found**

- Verify PDF contains tables
- Check if PDF is scanned (may need OCR)
- Try re-uploading

**Problem: Numbers incorrect**

- Edit table manually
- Check for merged cells in source
- Verify number format (commas, decimals)

### Export Issues

**Problem: Export fails**

- Resolve all conflicts first
- Check disk space
- Try different template
- Contact support

**Problem: Formulas not working**

- Verify "Include Formulas" was checked
- Check Excel version (2016+ required)
- Enable macros if prompted

### Getting Help

**Support Channels:**

- **Email:** <support@statementxl.com>
- **Live Chat:** Available 9 AM - 5 PM EST
- **Help Center:** <https://help.statementxl.com>
- **Community Forum:** <https://community.statementxl.com>

**When Contacting Support:**

- Include document ID
- Describe the issue
- Attach screenshots if possible
- Mention your browser/OS

---

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Upload Document | `Ctrl+U` | `Cmd+U` |
| Save Changes | `Ctrl+S` | `Cmd+S` |
| Export | `Ctrl+E` | `Cmd+E` |
| Search | `Ctrl+F` | `Cmd+F` |
| Help | `F1` | `F1` |
| Cancel | `Esc` | `Esc` |

---

## Glossary

- **GAAP:** Generally Accepted Accounting Principles
- **Line Item:** A single row in a financial statement
- **Mapping:** Connection between extracted data and template cell
- **OCR:** Optical Character Recognition (for scanned PDFs)
- **Template:** Pre-formatted Excel file structure
- **Conflict:** When multiple items map to the same location

---

**Need More Help?**

Visit our [Help Center](https://help.statementxl.com) or contact [support@statementxl.com](mailto:support@statementxl.com)

**Happy Extracting!** 🚀

---

**User Guide Version:** 1.0.0  
**Last Updated:** December 31, 2025
