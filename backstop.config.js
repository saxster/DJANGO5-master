/**
 * BackstopJS Visual Regression Testing Configuration
 * YOUTILITY Industrial Minimal Design System
 *
 * Tests visual consistency across:
 *   - Light and dark modes
 *   - Multiple viewports (mobile, tablet, desktop)
 *   - Key application pages
 *   - Component states
 *
 * Installation:
 *   npm install -g backstopjs
 *
 * Usage:
 *   backstop reference  - Create baseline screenshots
 *   backstop test       - Compare against baseline
 *   backstop approve    - Approve changes
 *   backstop openReport - View detailed report
 *
 * Documentation:
 *   https://github.com/garris/BackstopJS
 */

module.exports = {
  id: 'youtility_industrial_minimal',
  viewports: [
    {
      label: 'phone',
      width: 375,
      height: 667
    },
    {
      label: 'tablet',
      width: 768,
      height: 1024
    },
    {
      label: 'desktop',
      width: 1920,
      height: 1080
    }
  ],
  onBeforeScript: 'puppet/onBefore.js',
  onReadyScript: 'puppet/onReady.js',
  scenarios: [
    /* ========================================
       ADMIN PAGES
       ======================================== */
    {
      label: 'Admin Login - Light Mode',
      url: 'http://localhost:8000/admin/login/',
      referenceUrl: '',
      readySelector: '#login-form',
      delay: 500,
      misMatchThreshold: 0.1,
      requireSameDimensions: true
    },
    {
      label: 'Admin Login - Dark Mode',
      url: 'http://localhost:8000/admin/login/',
      onReadyScript: 'puppet/setDarkMode.js',
      readySelector: '#login-form',
      delay: 500,
      misMatchThreshold: 0.1
    },
    {
      label: 'Admin Dashboard - Light Mode',
      url: 'http://localhost:8000/admin/',
      onBeforeScript: 'puppet/login.js',
      readySelector: '#content',
      delay: 1000,
      misMatchThreshold: 0.1
    },
    {
      label: 'Admin Dashboard - Dark Mode',
      url: 'http://localhost:8000/admin/',
      onBeforeScript: 'puppet/login.js',
      onReadyScript: 'puppet/setDarkMode.js',
      readySelector: '#content',
      delay: 1000,
      misMatchThreshold: 0.1
    },
    {
      label: 'Admin Form Page',
      url: 'http://localhost:8000/admin/peoples/people/add/',
      onBeforeScript: 'puppet/login.js',
      readySelector: 'form',
      delay: 1000,
      misMatchThreshold: 0.1
    },
    {
      label: 'Admin List Page',
      url: 'http://localhost:8000/admin/peoples/people/',
      onBeforeScript: 'puppet/login.js',
      readySelector: '#changelist',
      delay: 1000,
      misMatchThreshold: 0.1
    },

    /* ========================================
       ERROR PAGES
       ======================================== */
    {
      label: 'Error 403 Page',
      url: 'http://localhost:8000/errors/403/',
      readySelector: '.error-container',
      delay: 500,
      misMatchThreshold: 0.1
    },
    {
      label: 'Error 500 Page',
      url: 'http://localhost:8000/errors/500/',
      readySelector: '.error-container',
      delay: 500,
      misMatchThreshold: 0.1
    },

    /* ========================================
       API DOCUMENTATION
       ======================================== */
    {
      label: 'Swagger UI - Light Mode',
      url: 'http://localhost:8000/api/docs/',
      readySelector: '#swagger-ui',
      delay: 2000,
      misMatchThreshold: 0.1
    },
    {
      label: 'Swagger UI - Dark Mode',
      url: 'http://localhost:8000/api/docs/',
      onReadyScript: 'puppet/setDarkMode.js',
      readySelector: '#swagger-ui',
      delay: 2000,
      misMatchThreshold: 0.1
    },

    /* ========================================
       STYLE GUIDE
       ======================================== */
    {
      label: 'Style Guide - Components',
      url: 'http://localhost:8000/styleguide/',
      readySelector: '.styleguide',
      delay: 1000,
      misMatchThreshold: 0.1
    },
    {
      label: 'Style Guide - Dark Mode',
      url: 'http://localhost:8000/styleguide/',
      onReadyScript: 'puppet/setDarkMode.js',
      readySelector: '.styleguide',
      delay: 1000,
      misMatchThreshold: 0.1
    }
  ],
  paths: {
    bitmaps_reference: 'tests/visual/backstop_data/bitmaps_reference',
    bitmaps_test: 'tests/visual/backstop_data/bitmaps_test',
    engine_scripts: 'tests/visual/backstop_data/engine_scripts',
    html_report: 'tests/visual/backstop_data/html_report',
    ci_report: 'tests/visual/backstop_data/ci_report'
  },
  report: ['browser', 'CI'],
  engine: 'puppeteer',
  engineOptions: {
    args: ['--no-sandbox']
  },
  asyncCaptureLimit: 5,
  asyncCompareLimit: 50,
  debug: false,
  debugWindow: false
};
