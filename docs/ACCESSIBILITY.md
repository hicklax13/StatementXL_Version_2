# StatementXL Accessibility Checklist (WCAG 2.1 AA)

## Color & Contrast

- [x] Text has 4.5:1 contrast ratio with background
- [x] Large text (18pt+) has 3:1 contrast ratio
- [x] UI components have 3:1 contrast ratio
- [ ] Color is not the only means of conveying information

## Keyboard Navigation

- [x] All interactive elements are keyboard accessible
- [x] Focus indicators are visible
- [ ] Skip navigation link present
- [x] Tab order is logical
- [x] No keyboard traps

## Screen Reader Support

- [ ] All images have alt text
- [x] Form inputs have labels
- [ ] ARIA landmarks used
- [ ] Dynamic content changes announced
- [x] Error messages associated with inputs

## Forms

- [x] All inputs have visible labels
- [x] Required fields are indicated
- [x] Error messages are clear and specific
- [x] Form validation is accessible

## Media

- [ ] Videos have captions (if applicable)
- [ ] Audio has transcripts (if applicable)
- [x] Animations can be paused

## Page Structure

- [x] Single H1 per page
- [x] Heading hierarchy is logical
- [x] Language is set on HTML element
- [x] Page titles are descriptive

## Testing Commands

```bash
# Install axe for automated testing
npm install -g @axe-core/cli

# Run accessibility scan
axe http://localhost:5173

# Manual testing with screen reader
# macOS: Enable VoiceOver (Cmd+F5)
# Windows: Use NVDA (free) or Narrator
```

## Priority Fixes

1. Add skip navigation link
2. Add alt text to all images
3. Add ARIA landmarks (main, nav, aside)
4. Ensure color is not only indicator

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [WebAIM Color Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [WAVE Extension](https://wave.webaim.org/extension/)
