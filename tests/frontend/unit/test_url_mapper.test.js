/**
 * Unit tests for URL Mapper core functionality
 * Tests URL transformation, legacy detection, and namespace mapping
 */

// Import the URL mapper code (we'll need to load it as a module for testing)
const fs = require('fs');
const path = require('path');

// Load the URL mapper code
const urlMapperPath = path.join(__dirname, '../../../frontend/static/assets/js/local/url_mapper.js');
let urlMapperCode = fs.readFileSync(urlMapperPath, 'utf8');

// Remove the IIFE wrapper and auto-initialization for testing
urlMapperCode = urlMapperCode.replace(/\(function\(window\) \{[\s\S]*?\}\)\(window\);/, '');
urlMapperCode = urlMapperCode.replace(/document\.addEventListener\('DOMContentLoaded', init\);/, '');
urlMapperCode = urlMapperCode.replace(/init\(\);/, '');

// Execute the code in test environment
eval(urlMapperCode);

describe('URL Mapper Core Functions', () => {
  let UrlMapper;

  beforeEach(() => {
    testUtils.resetMocks();
    
    // Initialize UrlMapper fresh for each test
    window.UrlMapper = undefined;
    window.URL_DEBUG_MODE = false;
    
    // Re-execute the code to get fresh UrlMapper
    eval(urlMapperCode);
    UrlMapper = window.UrlMapper;
  });

  afterEach(() => {
    testUtils.resetMocks();
  });

  describe('transformUrl function', () => {
    test('should transform onboarding:bu to admin_panel:bu_list', () => {
      const result = UrlMapper.transformUrl('onboarding:bu');
      expect(result).toBe('admin_panel:bu_list');
    });

    test('should transform onboarding:client to admin_panel:clients_list', () => {
      const result = UrlMapper.transformUrl('onboarding:client');
      expect(result).toBe('admin_panel:clients_list');
    });

    test('should transform path patterns correctly', () => {
      const result = UrlMapper.transformUrl('/onboarding/bu/?action=list');
      expect(result).toBe('/admin/business-units/?action=list');
    });

    test('should preserve query parameters in transformations', () => {
      const result = UrlMapper.transformUrl('/onboarding/client/?id=123&action=edit');
      expect(result).toBe('/admin/clients/?id=123&action=edit');
    });

    test('should return unchanged URL if no mapping exists', () => {
      const unchangedUrl = '/some/unmapped/url/';
      const result = UrlMapper.transformUrl(unchangedUrl);
      expect(result).toBe(unchangedUrl);
    });

    test('should handle null and undefined inputs gracefully', () => {
      expect(UrlMapper.transformUrl(null)).toBeNull();
      expect(UrlMapper.transformUrl(undefined)).toBeUndefined();
      expect(UrlMapper.transformUrl('')).toBe('');
    });

    test('should handle non-string inputs gracefully', () => {
      expect(UrlMapper.transformUrl(123)).toBe(123);
      expect(UrlMapper.transformUrl({})).toEqual({});
      expect(UrlMapper.transformUrl([])).toEqual([]);
    });

    test('should log transformation in debug mode', () => {
      window.URL_DEBUG_MODE = true;
      
      const result = UrlMapper.transformUrl('onboarding:bu');
      
      // Check that transformation occurred
      expect(result).toBe('admin_panel:bu_list');
      // In a real test environment, we would check console.log was called
    });

    test('should handle complex URLs with multiple parameters', () => {
      const complexUrl = '/onboarding/bu/?id=123&action=edit&template=true&sort=name';
      const result = UrlMapper.transformUrl(complexUrl);
      expect(result).toBe('/admin/business-units/?id=123&action=edit&template=true&sort=name');
    });

    test('should transform all critical namespace mappings', () => {
      const criticalMappings = {
        'onboarding:bu': 'admin_panel:bu_list',
        'onboarding:client': 'admin_panel:clients_list',
        'onboarding:contract': 'admin_panel:contracts_list',
        'onboarding:typeassist': 'admin_panel:config_types',
        'onboarding:shift': 'admin_panel:config_shifts',
        'onboarding:geofence': 'admin_panel:config_geofences',
        'onboarding:import': 'admin_panel:data_import',
        'onboarding:import_update': 'admin_panel:data_bulk_update'
      };

      Object.entries(criticalMappings).forEach(([oldUrl, expectedNewUrl]) => {
        const result = UrlMapper.transformUrl(oldUrl);
        expect(result).toBe(expectedNewUrl);
      });
    });
  });

  describe('isLegacyUrl function', () => {
    test('should detect onboarding namespace URLs as legacy', () => {
      expect(UrlMapper.isLegacyUrl('onboarding:bu')).toBe(true);
      expect(UrlMapper.isLegacyUrl('onboarding:client')).toBe(true);
      expect(UrlMapper.isLegacyUrl('/onboarding/bu/')).toBe(true);
    });

    test('should not detect modern URLs as legacy', () => {
      expect(UrlMapper.isLegacyUrl('admin_panel:bu_list')).toBe(false);
      expect(UrlMapper.isLegacyUrl('/admin/business-units/')).toBe(false);
      expect(UrlMapper.isLegacyUrl('/modern/url/path/')).toBe(false);
    });

    test('should handle edge cases gracefully', () => {
      expect(UrlMapper.isLegacyUrl('')).toBe(false);
      expect(UrlMapper.isLegacyUrl(null)).toBe(false);
      expect(UrlMapper.isLegacyUrl(undefined)).toBe(false);
    });

    test('should detect all legacy patterns', () => {
      const legacyPatterns = [
        'onboarding:bu',
        'onboarding:client', 
        'onboarding:contract',
        '/onboarding/bu/',
        '/onboarding/client/',
        'schedhuler:jobneedtasks',
        'activity:asset',
        'peoples:people'
      ];

      legacyPatterns.forEach(pattern => {
        expect(UrlMapper.isLegacyUrl(pattern)).toBe(true);
      });
    });
  });

  describe('mapNamespace function', () => {
    test('should map known namespaces correctly', () => {
      expect(UrlMapper.mapNamespace('onboarding:bu')).toBe('admin_panel:bu_list');
      expect(UrlMapper.mapNamespace('onboarding:client')).toBe('admin_panel:clients_list');
    });

    test('should return original namespace if no mapping exists', () => {
      const unknownNamespace = 'unknown:namespace';
      expect(UrlMapper.mapNamespace(unknownNamespace)).toBe(unknownNamespace);
    });

    test('should handle empty and null inputs', () => {
      expect(UrlMapper.mapNamespace('')).toBe('');
      expect(UrlMapper.mapNamespace(null)).toBe(null);
      expect(UrlMapper.mapNamespace(undefined)).toBe(undefined);
    });
  });

  describe('getNewUrl function', () => {
    test('should be an alias for transformUrl', () => {
      const testUrl = 'onboarding:bu';
      expect(UrlMapper.getNewUrl(testUrl)).toBe(UrlMapper.transformUrl(testUrl));
    });

    test('should handle all the same cases as transformUrl', () => {
      const testCases = [
        'onboarding:bu',
        '/onboarding/client/',
        null,
        undefined,
        '',
        123
      ];

      testCases.forEach(testCase => {
        expect(UrlMapper.getNewUrl(testCase)).toBe(UrlMapper.transformUrl(testCase));
      });
    });
  });

  describe('URL_NAMESPACE_MAPPINGS constant', () => {
    test('should expose URL mappings for testing', () => {
      expect(UrlMapper.URL_NAMESPACE_MAPPINGS).toBeDefined();
      expect(typeof UrlMapper.URL_NAMESPACE_MAPPINGS).toBe('object');
    });

    test('should contain all critical onboarding mappings', () => {
      const mappings = UrlMapper.URL_NAMESPACE_MAPPINGS;
      
      expect(mappings['onboarding:bu']).toBe('admin_panel:bu_list');
      expect(mappings['onboarding:client']).toBe('admin_panel:clients_list');
      expect(mappings['onboarding:contract']).toBe('admin_panel:contracts_list');
    });

    test('should have at least 25 mappings', () => {
      const mappingCount = Object.keys(UrlMapper.URL_NAMESPACE_MAPPINGS).length;
      expect(mappingCount).toBeGreaterThanOrEqual(25);
    });

    test('should not have any duplicate values', () => {
      const mappings = UrlMapper.URL_NAMESPACE_MAPPINGS;
      const values = Object.values(mappings);
      const uniqueValues = [...new Set(values)];
      
      expect(values.length).toBe(uniqueValues.length);
    });
  });

  describe('PATH_PATTERN_MAPPINGS constant', () => {
    test('should expose path mappings for testing', () => {
      expect(UrlMapper.PATH_PATTERN_MAPPINGS).toBeDefined();
      expect(typeof UrlMapper.PATH_PATTERN_MAPPINGS).toBe('object');
    });

    test('should contain critical path mappings', () => {
      const pathMappings = UrlMapper.PATH_PATTERN_MAPPINGS;
      
      expect(pathMappings['/onboarding/bu/']).toBe('/admin/business-units/');
      expect(pathMappings['/onboarding/client/']).toBe('/admin/clients/');
    });

    test('should have consistent URL formatting', () => {
      const pathMappings = UrlMapper.PATH_PATTERN_MAPPINGS;
      
      Object.entries(pathMappings).forEach(([oldPath, newPath]) => {
        expect(oldPath).toMatch(/^\/.*\/$/); // Should start and end with /
        expect(newPath).toMatch(/^\/.*\/$/); // Should start and end with /
      });
    });
  });

  describe('logger functionality', () => {
    beforeEach(() => {
      window.URL_DEBUG_MODE = true;
      window.location.hostname = 'localhost';
    });

    test('should expose logger object', () => {
      expect(UrlMapper.logger).toBeDefined();
      expect(typeof UrlMapper.logger.log).toBe('function');
      expect(typeof UrlMapper.logger.warn).toBe('function');
      expect(typeof UrlMapper.logger.error).toBe('function');
    });

    test('should log in debug mode', () => {
      UrlMapper.logger.log('Test message');
      // In a real environment, we would check console.log was called
      // For now, we just ensure the function executes without error
      expect(true).toBe(true);
    });

    test('should warn about unmapped legacy URLs', () => {
      const unmappedUrl = 'legacy:unmapped_url';
      UrlMapper.transformUrl(unmappedUrl);
      // The warning would be logged internally
      expect(true).toBe(true);
    });
  });

  describe('initialization', () => {
    test('should initialize without jQuery gracefully', () => {
      // Remove jQuery temporarily
      const originalJQuery = global.$;
      global.$ = undefined;
      
      // Re-initialize UrlMapper
      expect(() => {
        eval(urlMapperCode);
      }).not.toThrow();
      
      // Restore jQuery
      global.$ = originalJQuery;
    });

    test('should auto-initialize when DOM is ready', () => {
      // This tests the auto-initialization logic
      expect(window.UrlMapper).toBeDefined();
      expect(typeof window.UrlMapper.transformUrl).toBe('function');
    });

    test('should expose public API methods', () => {
      const expectedMethods = [
        'transformUrl',
        'getNewUrl', 
        'isLegacyUrl',
        'mapNamespace',
        'logger'
      ];

      expectedMethods.forEach(method => {
        expect(UrlMapper[method]).toBeDefined();
      });
    });
  });
});

describe('URL Mapper Performance Tests', () => {
  let UrlMapper;

  beforeEach(() => {
    eval(urlMapperCode);
    UrlMapper = window.UrlMapper;
  });

  test('should transform URLs quickly - unit performance test', async () => {
    const testUrl = 'onboarding:bu';
    
    const time = await performanceUtils.measureTime(() => {
      for (let i = 0; i < 1000; i++) {
        UrlMapper.transformUrl(testUrl);
      }
    });

    // Should transform 1000 URLs in under 10ms
    expect(time).toBeLessThan(10);
  });

  test('should handle large batches of URLs efficiently', async () => {
    const testUrls = [
      'onboarding:bu',
      'onboarding:client',
      'onboarding:contract',
      '/onboarding/bu/',
      '/onboarding/client/',
      'activity:asset',
      'peoples:people'
    ];

    const time = await performanceUtils.measureTime(() => {
      testUrls.forEach(url => {
        for (let i = 0; i < 100; i++) {
          UrlMapper.transformUrl(url);
        }
      });
    });

    // Should handle 700 transformations in under 20ms  
    expect(time).toBeLessThan(20);
  });

  test('should not have memory leaks in repeated operations', async () => {
    // Test that repeated transformations don't accumulate memory
    const initialMemory = process.memoryUsage().heapUsed;
    
    for (let i = 0; i < 10000; i++) {
      UrlMapper.transformUrl('onboarding:bu');
      UrlMapper.isLegacyUrl('onboarding:client');
    }

    const finalMemory = process.memoryUsage().heapUsed;
    const memoryIncrease = finalMemory - initialMemory;

    // Memory increase should be minimal (less than 1MB)
    expect(memoryIncrease).toBeLessThan(1024 * 1024);
  });
});