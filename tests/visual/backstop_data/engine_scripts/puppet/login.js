/**
 * BackstopJS - Auto Login
 * Logs into Django admin before taking screenshots
 */

module.exports = async (page, scenario, vp) => {
  console.log('Logging into admin for ' + scenario.label);

  // Navigate to login page
  await page.goto('http://localhost:8000/admin/login/', {
    waitUntil: 'networkidle0'
  });

  // Fill login form
  await page.type('#id_username', 'admin');
  await page.type('#id_password', 'admin123');  // Use test credentials

  // Submit form
  await Promise.all([
    page.click('input[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle0' })
  ]);

  console.log('Login successful');
};
