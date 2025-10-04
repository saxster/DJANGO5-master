/**
 * BackstopJS - Load Cookies
 * Loads cookies for authenticated sessions
 */

const fs = require('fs');

module.exports = async (page, scenario) => {
  const cookiePath = 'tests/visual/backstop_data/engine_scripts/cookies.json';

  // Check if cookies file exists
  if (fs.existsSync(cookiePath)) {
    const cookies = JSON.parse(fs.readFileSync(cookiePath));

    // Set cookies
    for (const cookie of cookies) {
      await page.setCookie(cookie);
    }

    console.log('Cookies loaded');
  }
};
