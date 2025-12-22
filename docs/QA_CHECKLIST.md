# StatementXL QA Test Plan

## Critical User Flows

### Flow 1: User Registration & Login
- [ ] Navigate to /register
- [ ] Enter email, password (valid)
- [ ] Submit and verify redirect to dashboard
- [ ] Logout
- [ ] Login with same credentials
- [ ] Verify dashboard loads

### Flow 2: PDF Upload → Extraction
- [ ] Click Upload
- [ ] Drag & drop a PDF
- [ ] Verify upload progress
- [ ] Wait for processing
- [ ] Verify extraction results appear
- [ ] Check table data accuracy

### Flow 3: Template Mapping
- [ ] View extracted data
- [ ] Select a template
- [ ] Map columns to template fields
- [ ] Resolve any conflicts
- [ ] Save mapping
- [ ] Verify mapping persisted

### Flow 4: Excel Export
- [ ] Select mapped document
- [ ] Click Export
- [ ] Choose Excel format
- [ ] Download file
- [ ] Open in Excel
- [ ] Verify data accuracy

## Edge Cases

### Empty States
- [ ] Dashboard with no documents
- [ ] Template library empty
- [ ] Search with no results

### Error States
- [ ] Invalid file type upload
- [ ] Oversized file upload (>50MB)
- [ ] Network error during upload
- [ ] Session expired

### Validation
- [ ] Short password (test 400 error)
- [ ] Invalid email format
- [ ] Empty required fields
- [ ] SQL injection attempt

## Performance

- [ ] Page load < 2 seconds
- [ ] PDF upload response < 500ms
- [ ] Large PDF (50+ pages) processes

## Security

- [ ] Protected routes redirect to login
- [ ] Invalid token rejected
- [ ] Rate limiting triggers at limit
- [ ] XSS input is escaped

## Bug Tracking

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| P0 | Critical | Blocks core flow | Must fix |
| P1 | High | Major issue | Should fix |
| P2 | Medium | Minor issue | Nice to fix |
| P3 | Low | Cosmetic | Backlog |

## Sign-Off

| Tester | Date | Result |
|--------|------|--------|
| | | Pass / Fail |
