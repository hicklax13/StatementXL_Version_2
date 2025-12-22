# Browser & Device Compatibility Matrix

## Supported Browsers

| Browser | Minimum Version | Status |
|---------|-----------------|--------|
| Chrome | 120+ | ✅ Fully Supported |
| Firefox | 120+ | ✅ Fully Supported |
| Safari | 17+ | ✅ Fully Supported |
| Edge | 120+ | ✅ Fully Supported |
| Opera | 100+ | ⚠️ Not Tested |
| IE 11 | - | ❌ Not Supported |

## Supported Devices

| Device | Screen Size | Status |
|--------|-------------|--------|
| Desktop | 1920x1080 | ✅ Primary Target |
| Desktop | 1366x768 | ✅ Supported |
| MacBook | 2560x1600 | ✅ Supported |
| Laptop | 1280x720 | ✅ Supported |
| iPad Pro | 1024x1366 | ⚠️ Functional |
| iPad | 768x1024 | ⚠️ Functional |
| Mobile | 375x667 | ⚠️ Responsive View |

## Known Issues

### Safari
- File upload drag-drop may be less responsive
- Use click-to-upload as fallback

### Firefox
- PDF preview uses browser's built-in viewer
- Some tooltip positioning differences

### Mobile
- Not optimized for mobile use
- Recommend desktop for best experience
- PDF upload works but review is difficult

## Testing Checklist

### Desktop Browsers
- [ ] Chrome - Login flow
- [ ] Chrome - PDF upload
- [ ] Chrome - Table extraction
- [ ] Chrome - Excel export
- [ ] Firefox - Login flow
- [ ] Firefox - PDF upload
- [ ] Safari - Login flow
- [ ] Safari - PDF upload
- [ ] Edge - Login flow
- [ ] Edge - PDF upload

### Responsive Design
- [ ] 1920px - Full layout
- [ ] 1366px - Standard layout
- [ ] 1024px - Tablet layout
- [ ] 768px - Collapsed sidebar
- [ ] 375px - Mobile layout

## Browser Testing Tools

```bash
# BrowserStack (recommended)
# https://www.browserstack.com/

# Local testing with Playwright
npm install -D playwright
npx playwright test --browser=all

# Screenshots across browsers
npx playwright screenshot http://localhost:5173 --browser=firefox screenshot.png
```
