/**
 * BackstopJS - Ready Script
 * Runs after page loads, before screenshot
 */

module.exports = async (page, scenario, vp) => {
  console.log('SCENARIO > ' + scenario.label);

  // Wait for fonts to load
  await page.evaluateHandle('document.fonts.ready');

  // Wait for any animations to complete
  await page.waitForTimeout(500);

  // Disable smooth scrolling for consistent screenshots
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'auto';
  });

  // Remove animated elements that cause flakiness
  await page.evaluate(() => {
    const animatedElements = document.querySelectorAll('.animate, [data-animate]');
    animatedElements.forEach(el => {
      el.style.animation = 'none';
      el.style.transition = 'none';
    });
  });
};
