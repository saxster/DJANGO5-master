/**
 * Performance and edge case tests for URL mapping
 * Tests URL transformation speed, error handling, and edge cases
 */

const fs = require('fs');
const path = require('path');

// Load URL mapper for performance testing
const urlMapperPath = path.join(__dirname, '../../../frontend/static/assets/js/local/url_mapper.js');
let urlMapperCode = fs.readFileSync(urlMapperPath, 'utf8');
urlMapperCode = urlMapperCode.replace(/\(function\(window\) \{[\s\S]*?\}\)\(window\);/, '');
urlMapperCode = urlMapperCode.replace(/document\.addEventListener\('DOMContentLoaded', init\);/, '');
urlMapperCode = urlMapperCode.replace(/init\(\);/, '');

describe('Performance Tests', () => {
  let UrlMapper;

  beforeEach(() => {
    testUtils.resetMocks();
    window.UrlMapper = undefined;
    window.URL_DEBUG_MODE = false;
    eval(urlMapperCode);
    UrlMapper = window.UrlMapper;
  });

  afterEach(() => {
    testUtils.resetMocks();
  });

  describe('URL Transformation Performance', () => {
    test('should transform single URL in under 1ms', async () => {
      const testUrl = 'onboarding:bu';
      
      const time = await performanceUtils.measureTime(() => {
        UrlMapper.transformUrl(testUrl);
      });

      expect(time).toBeLessThan(1);
    });

    test('should transform 1000 URLs in under 10ms', async () => {
      const testUrl = 'onboarding:client';
      
      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 1000; i++) {
          UrlMapper.transformUrl(testUrl);
        }
      });

      expect(time).toBeLessThan(10);
    });

    test('should handle mixed URL types efficiently', async () => {
      const urls = [
        'onboarding:bu',
        'onboarding:client',
        'onboarding:contract',
        '/onboarding/bu/',
        '/onboarding/client/',
        'activity:asset',
        'peoples:people',
        '/admin/business-units/',
        '/modern/url/path/',
        'https://external.com/api/'
      ];

      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 100; i++) {
          urls.forEach(url => UrlMapper.transformUrl(url));
        }
      });

      // 1000 mixed transformations should be very fast
      expect(time).toBeLessThan(20);
    });

    test('should not degrade performance with repeated mappings', async () => {
      const testUrl = 'onboarding:bu';
      
      // Warm up
      for (let i = 0; i < 100; i++) {
        UrlMapper.transformUrl(testUrl);
      }
      
      // Measure first batch
      const time1 = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 1000; i++) {
          UrlMapper.transformUrl(testUrl);
        }
      });
      
      // Measure second batch after many operations
      const time2 = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 1000; i++) {
          UrlMapper.transformUrl(testUrl);
        }
      });
      
      // Performance should not degrade significantly
      expect(time2).toBeLessThan(time1 * 1.5); // Allow 50% variance
    });

    test('should perform well with complex URLs', async () => {
      const complexUrls = [
        '/onboarding/bu/?id=123&action=edit&template=true&sort=name&filter=active&page=2',
        'onboarding:client?search=test&category=premium&status=enabled&limit=50',
        '/onboarding/contract/?client_id=456&type=annual&renewal_date=2024-01-01&auto_renew=true'
      ];

      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 500; i++) {
          complexUrls.forEach(url => UrlMapper.transformUrl(url));
        }
      });

      // 1500 complex URL transformations
      expect(time).toBeLessThan(30);
    });

    test('should handle concurrent transformations efficiently', async () => {
      const urls = Array.from({ length: 100 }, (_, i) => `onboarding:bu?id=${i}`);
      
      const promises = urls.map(url => 
        performanceUtils.measureTime(() => UrlMapper.transformUrl(url))
      );
      
      const times = await Promise.all(promises);
      const avgTime = times.reduce((sum, time) => sum + time, 0) / times.length;
      
      expect(avgTime).toBeLessThan(1);
    });
  });

  describe('Memory Performance', () => {
    test('should not leak memory during repeated operations', () => {
      const initialMemory = process.memoryUsage().heapUsed;
      
      // Perform many operations
      for (let i = 0; i < 10000; i++) {
        UrlMapper.transformUrl('onboarding:bu');
        UrlMapper.isLegacyUrl('onboarding:client');
        UrlMapper.mapNamespace('onboarding:contract');
      }
      
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
      
      const finalMemory = process.memoryUsage().heapUsed;
      const memoryIncrease = finalMemory - initialMemory;
      
      // Memory increase should be minimal (less than 1MB)
      expect(memoryIncrease).toBeLessThan(1024 * 1024);
    });

    test('should not accumulate state in repeated calls', () => {
      const testUrl = 'onboarding:bu';
      
      // Call transformation many times
      for (let i = 0; i < 1000; i++) {
        const result = UrlMapper.transformUrl(testUrl);
        expect(result).toBe('admin_panel:bu_list');
      }
      
      // Result should be consistent - no state accumulation
      const finalResult = UrlMapper.transformUrl(testUrl);
      expect(finalResult).toBe('admin_panel:bu_list');
    });
  });

  describe('Scalability Performance', () => {
    test('should handle large URL mapping sets efficiently', async () => {
      // Simulate adding more mappings to the URL_NAMESPACE_MAPPINGS
      const largeMappingSet = { ...UrlMapper.URL_NAMESPACE_MAPPINGS };
      
      // Add 1000 more mappings
      for (let i = 0; i < 1000; i++) {
        largeMappingSet[`test:namespace_${i}`] = `new:namespace_${i}`;
      }
      
      // Temporarily replace mappings
      const originalMappings = UrlMapper.URL_NAMESPACE_MAPPINGS;
      UrlMapper.URL_NAMESPACE_MAPPINGS = largeMappingSet;
      
      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 100; i++) {
          UrlMapper.transformUrl('onboarding:bu');
          UrlMapper.transformUrl(`test:namespace_${i % 100}`);
        }
      });
      
      // Restore original mappings
      UrlMapper.URL_NAMESPACE_MAPPINGS = originalMappings;
      
      // Should still be fast with larger mapping set
      expect(time).toBeLessThan(50);
    });
  });
});

describe('Edge Case Tests', () => {
  let UrlMapper;

  beforeEach(() => {
    testUtils.resetMocks();
    window.UrlMapper = undefined;
    eval(urlMapperCode);
    UrlMapper = window.UrlMapper;
  });

  describe('Input Edge Cases', () => {
    test('should handle null and undefined gracefully', () => {
      expect(() => UrlMapper.transformUrl(null)).not.toThrow();
      expect(() => UrlMapper.transformUrl(undefined)).not.toThrow();
      expect(() => UrlMapper.isLegacyUrl(null)).not.toThrow();
      expect(() => UrlMapper.isLegacyUrl(undefined)).not.toThrow();
      
      expect(UrlMapper.transformUrl(null)).toBeNull();
      expect(UrlMapper.transformUrl(undefined)).toBeUndefined();
      expect(UrlMapper.isLegacyUrl(null)).toBe(false);
      expect(UrlMapper.isLegacyUrl(undefined)).toBe(false);
    });

    test('should handle empty strings', () => {
      expect(UrlMapper.transformUrl('')).toBe('');
      expect(UrlMapper.isLegacyUrl('')).toBe(false);
      expect(UrlMapper.mapNamespace('')).toBe('');
    });

    test('should handle non-string inputs', () => {
      const nonStringInputs = [123, true, false, [], {}, Symbol('test')];
      
      nonStringInputs.forEach(input => {
        expect(() => UrlMapper.transformUrl(input)).not.toThrow();
        expect(() => UrlMapper.isLegacyUrl(input)).not.toThrow();
        
        // Should return input unchanged for non-strings
        expect(UrlMapper.transformUrl(input)).toBe(input);
        expect(UrlMapper.isLegacyUrl(input)).toBe(false);
      });
    });

    test('should handle very long URLs', () => {
      const longUrl = 'onboarding:bu' + '?param=value&'.repeat(1000) + 'end=true';
      
      expect(() => UrlMapper.transformUrl(longUrl)).not.toThrow();
      
      const result = UrlMapper.transformUrl(longUrl);
      expect(result).toContain('admin_panel:bu_list');
      expect(result.length).toBeGreaterThan(longUrl.length - 50); // Should preserve most content
    });

    test('should handle special characters', () => {
      const specialCharUrls = [
        'onboarding:bu?name=John%20Doe&email=test%40example.com',
        'onboarding:client?search=München&category=café',
        '/onboarding/bu/?data={"name":"test","value":123}',
        'onboarding:contract?filter=price>100&sort=name<>asc'
      ];

      specialCharUrls.forEach(url => {
        expect(() => UrlMapper.transformUrl(url)).not.toThrow();
        
        const result = UrlMapper.transformUrl(url);
        expect(result).not.toBe(url); // Should be transformed
        expect(result.length).toBeGreaterThan(0);
      });
    });

    test('should handle malformed URLs', () => {
      const malformedUrls = [
        'onboarding:',
        ':bu',
        'onboarding::bu',
        'onboarding:bu:',
        '/onboarding//bu/',
        'onboarding:bu?',
        'onboarding:bu?&',
        'onboarding:bu?param&'
      ];

      malformedUrls.forEach(url => {
        expect(() => UrlMapper.transformUrl(url)).not.toThrow();
        expect(() => UrlMapper.isLegacyUrl(url)).not.toThrow();
        
        // Should handle malformed URLs gracefully
        const result = UrlMapper.transformUrl(url);
        expect(typeof result).toBe('string');
      });
    });

    test('should handle unicode characters', () => {
      const unicodeUrls = [
        'onboarding:bu?name=José&location=São Paulo',
        'onboarding:client?search=北京&category=测试',
        '/onboarding/bu/?comment=This is a test with émojis 🚀'
      ];

      unicodeUrls.forEach(url => {
        expect(() => UrlMapper.transformUrl(url)).not.toThrow();
        
        const result = UrlMapper.transformUrl(url);
        expect(result).toContain('admin_panel'); // Should be transformed
      });
    });
  });

  describe('Boundary Cases', () => {
    test('should handle URLs at maximum typical length', () => {
      // URLs up to 2048 characters (typical browser limit)
      const maxLengthUrl = 'onboarding:bu?' + 'a=1&'.repeat(400) + 'final=true';
      
      expect(maxLengthUrl.length).toBeLessThanOrEqual(2048);
      expect(() => UrlMapper.transformUrl(maxLengthUrl)).not.toThrow();
      
      const result = UrlMapper.transformUrl(maxLengthUrl);
      expect(result).toContain('admin_panel:bu_list');
    });

    test('should handle minimum URL patterns', () => {
      const minimalUrls = [
        'a:b',
        'x',
        '/',
        '?',
        '#'
      ];

      minimalUrls.forEach(url => {
        expect(() => UrlMapper.transformUrl(url)).not.toThrow();
        expect(() => UrlMapper.isLegacyUrl(url)).not.toThrow();
      });
    });

    test('should handle URL patterns that partially match', () => {
      const partialMatches = [
        'onboarding', // Missing colon
        'onboarding:', // Missing namespace
        'boarding:bu', // Missing prefix
        'onboarding:buffer', // Similar but not exact
        '/onboarding/', // Missing specific path
        'xonboarding:bu', // Extra prefix
        'onboarding:bux' // Extra suffix
      ];

      partialMatches.forEach(url => {
        const result = UrlMapper.transformUrl(url);
        const isLegacy = UrlMapper.isLegacyUrl(url);
        
        // Should handle gracefully but not transform incorrectly
        expect(typeof result).toBe('string');
        expect(typeof isLegacy).toBe('boolean');
      });
    });
  });

  describe('State Edge Cases', () => {
    test('should handle multiple URL mappers', () => {
      // Create second instance
      const secondMapper = { ...UrlMapper };
      
      // Both should work independently
      expect(UrlMapper.transformUrl('onboarding:bu')).toBe('admin_panel:bu_list');
      expect(secondMapper.transformUrl('onboarding:bu')).toBe('admin_panel:bu_list');
    });

    test('should handle URL mapper without initialization', () => {
      // Remove URL mapper temporarily
      const originalMapper = window.UrlMapper;
      window.UrlMapper = undefined;
      
      // Functions should still exist and not crash
      expect(() => {
        if (typeof window.UrlMapper !== 'undefined') {
          window.UrlMapper.transformUrl('test');
        }
      }).not.toThrow();
      
      // Restore
      window.UrlMapper = originalMapper;
    });

    test('should handle debug mode changes during runtime', () => {
      window.URL_DEBUG_MODE = false;
      UrlMapper.transformUrl('onboarding:bu');
      
      window.URL_DEBUG_MODE = true;
      UrlMapper.transformUrl('onboarding:client');
      
      window.URL_DEBUG_MODE = false;
      UrlMapper.transformUrl('onboarding:contract');
      
      // Should not crash during debug mode changes
      expect(true).toBe(true);
    });
  });
});

describe('Error Handling Tests', () => {
  let UrlMapper;

  beforeEach(() => {
    testUtils.resetMocks();
    window.UrlMapper = undefined;
    eval(urlMapperCode);
    UrlMapper = window.UrlMapper;
  });

  describe('Graceful Degradation', () => {
    test('should work without jQuery', () => {
      const originalJQuery = global.$;
      global.$ = undefined;
      
      // URL mapper should still work for basic functionality
      expect(() => UrlMapper.transformUrl('onboarding:bu')).not.toThrow();
      expect(UrlMapper.transformUrl('onboarding:bu')).toBe('admin_panel:bu_list');
      
      global.$ = originalJQuery;
    });

    test('should handle missing console gracefully', () => {
      const originalConsole = global.console;
      global.console = undefined;
      
      window.URL_DEBUG_MODE = true;
      
      expect(() => {
        UrlMapper.transformUrl('onboarding:bu');
      }).not.toThrow();
      
      global.console = originalConsole;
    });

    test('should handle missing window properties', () => {
      const originalLocation = window.location;
      window.location = undefined;
      
      expect(() => {
        UrlMapper.transformUrl('onboarding:bu');
      }).not.toThrow();
      
      window.location = originalLocation;
    });
  });

  describe('AJAX Error Handling', () => {
    test('should handle AJAX failures gracefully', () => {
      global.$.ajax = jest.fn(() => {
        throw new Error('AJAX failed');
      });

      // This would normally be tested in an environment where AJAX interception is active
      expect(() => {
        // Simulate AJAX call that goes through URL mapper
        const transformedUrl = UrlMapper.transformUrl('onboarding:bu');
        expect(transformedUrl).toBe('admin_panel:bu_list');
      }).not.toThrow();
    });

    test('should log AJAX errors appropriately', () => {
      window.URL_DEBUG_MODE = true;
      
      // Simulate AJAX error logging
      expect(() => {
        UrlMapper.logger.error('Test AJAX error', 'Details');
      }).not.toThrow();
      
      // In real environment, would check that console.error was called
    });
  });

  describe('Network Error Scenarios', () => {
    test('should handle offline scenarios', () => {
      // Simulate offline state
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false
      });

      // URL transformation should still work offline
      expect(UrlMapper.transformUrl('onboarding:bu')).toBe('admin_panel:bu_list');
      expect(UrlMapper.isLegacyUrl('onboarding:client')).toBe(true);

      // Restore online state
      navigator.onLine = true;
    });

    test('should handle slow network conditions', async () => {
      // URL transformation itself should not be affected by network
      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 100; i++) {
          UrlMapper.transformUrl('onboarding:bu');
        }
      });

      // Should be fast regardless of network conditions
      expect(time).toBeLessThan(10);
    });
  });

  describe('Data Corruption Scenarios', () => {
    test('should handle corrupted mapping data', () => {
      // Simulate corrupted URL mappings
      const originalMappings = UrlMapper.URL_NAMESPACE_MAPPINGS;
      
      // Test with null mappings
      UrlMapper.URL_NAMESPACE_MAPPINGS = null;
      expect(() => UrlMapper.transformUrl('onboarding:bu')).not.toThrow();
      
      // Test with undefined mappings
      UrlMapper.URL_NAMESPACE_MAPPINGS = undefined;
      expect(() => UrlMapper.transformUrl('onboarding:bu')).not.toThrow();
      
      // Test with empty mappings
      UrlMapper.URL_NAMESPACE_MAPPINGS = {};
      const result = UrlMapper.transformUrl('onboarding:bu');
      expect(result).toBe('onboarding:bu'); // Should return unchanged
      
      // Restore
      UrlMapper.URL_NAMESPACE_MAPPINGS = originalMappings;
    });

    test('should handle circular references', () => {
      const originalMappings = UrlMapper.URL_NAMESPACE_MAPPINGS;
      
      // Create circular reference
      UrlMapper.URL_NAMESPACE_MAPPINGS = {
        'a:b': 'c:d',
        'c:d': 'a:b' // Circular reference
      };
      
      expect(() => UrlMapper.transformUrl('a:b')).not.toThrow();
      
      // Restore
      UrlMapper.URL_NAMESPACE_MAPPINGS = originalMappings;
    });
  });

  describe('Browser Compatibility Edge Cases', () => {
    test('should handle old browser environments', () => {
      // Simulate old browser without modern features
      const originalPromise = global.Promise;
      const originalSymbol = global.Symbol;
      
      global.Promise = undefined;
      global.Symbol = undefined;
      
      expect(() => {
        UrlMapper.transformUrl('onboarding:bu');
      }).not.toThrow();
      
      global.Promise = originalPromise;
      global.Symbol = originalSymbol;
    });

    test('should handle strict mode differences', () => {
      'use strict';
      
      expect(() => {
        UrlMapper.transformUrl('onboarding:bu');
        UrlMapper.isLegacyUrl('onboarding:client');
      }).not.toThrow();
    });
  });

  describe('Concurrent Access Edge Cases', () => {
    test('should handle multiple simultaneous transformations', async () => {
      const promises = [];
      
      for (let i = 0; i < 100; i++) {
        promises.push(new Promise(resolve => {
          setTimeout(() => {
            resolve(UrlMapper.transformUrl(`onboarding:bu?id=${i}`));
          }, Math.random() * 10);
        }));
      }
      
      const results = await Promise.all(promises);
      
      // All results should be consistent
      results.forEach(result => {
        expect(result).toContain('admin_panel:bu_list');
      });
    });

    test('should handle rapid successive calls', () => {
      // Rapid fire calls
      const results = [];
      
      for (let i = 0; i < 1000; i++) {
        results.push(UrlMapper.transformUrl('onboarding:bu'));
      }
      
      // All results should be identical
      const firstResult = results[0];
      results.forEach(result => {
        expect(result).toBe(firstResult);
      });
    });
  });
});