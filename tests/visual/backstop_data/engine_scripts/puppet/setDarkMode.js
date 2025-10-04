/**
 * BackstopJS - Set Dark Mode
 * Sets dark mode before screenshot
 */

module.exports = async (page, scenario, vp) => {
  console.log('Setting dark mode for ' + scenario.label);

  // Set dark mode via theme manager
  await page.evaluate(() => {
    if (window.themeManager) {
      window.themeManager.setTheme('dark');
    } else {
      // Fallback: set class directly
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  });

  // Wait for theme transition
  await page.waitForTimeout(300);
};
