/**
 * BackstopJS - Before Script
 * Runs before each scenario
 */

module.exports = async (page, scenario, vp) => {
  console.log('SCENARIO > ' + scenario.label);
  await require('./loadCookies')(page, scenario);
};
