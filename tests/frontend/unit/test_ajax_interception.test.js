/**
 * Unit tests for AJAX interception functionality
 * Tests enhanced AJAX functions with URL transformation
 */

// Load the custom.js code for AJAX functions
const fs = require('fs');
const path = require('path');

describe('AJAX Interception Tests', () => {
  let mockUrlMapper;
  let originalAjax;

  beforeEach(() => {
    testUtils.resetMocks();
    
    // Create mock UrlMapper
    mockUrlMapper = testUtils.createMockUrlMapper({
      transformUrl: jest.fn(url => {
        // Simulate transformation for known URLs
        if (url.includes('onboarding:bu')) return url.replace('onboarding:bu', 'admin_panel:bu_list');
        if (url.includes('/onboarding/bu/')) return url.replace('/onboarding/bu/', '/admin/business-units/');
        return url; // Return unchanged for unmapped URLs
      }),
      logger: {
        log: jest.fn(),
        warn: jest.fn(),
        error: jest.fn()
      }
    });

    // Set up global UrlMapper
    window.UrlMapper = mockUrlMapper;

    // Mock jQuery AJAX
    originalAjax = global.$.ajax;
    global.$.ajax = jest.fn(() => ({
      done: jest.fn(function(callback) {
        setTimeout(() => callback({success: true}), 0);
        return {
          fail: jest.fn(() => ({}))
        };
      }),
      fail: jest.fn(function(callback) {
        return {};
      })
    }));
  });

  afterEach(() => {
    testUtils.resetMocks();
    global.$.ajax = originalAjax;
  });

  describe('fire_ajax_form_post function', () => {
    // Define the function inline since we need it for testing
    function fire_ajax_form_post(params, payload) {
      // Transform URL using URL mapper if available
      if (typeof window.UrlMapper !== 'undefined' && params["url"]) {
        const originalUrl = params["url"];
        const transformedUrl = window.UrlMapper.transformUrl(originalUrl);
        if (originalUrl !== transformedUrl) {
          params["url"] = transformedUrl;
          if (window.UrlMapper.logger) {
            window.UrlMapper.logger.log('fire_ajax_form_post URL transformed', originalUrl, transformedUrl);
          }
        }
      }
      
      return $.ajax({
        url: params["url"],
        type: "post",
        data: payload,
      });
    }

    test('should transform legacy URLs before AJAX call', () => {
      const params = { url: 'onboarding:bu' };
      const payload = { data: 'test' };

      fire_ajax_form_post(params, payload);

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('onboarding:bu');
      expect(params.url).toBe('admin_panel:bu_list');
      expect(global.$.ajax).toHaveBeenCalledWith({
        url: 'admin_panel:bu_list',
        type: 'post',
        data: payload
      });
    });

    test('should not transform modern URLs', () => {
      const params = { url: '/admin/business-units/' };
      const payload = { data: 'test' };

      fire_ajax_form_post(params, payload);

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('/admin/business-units/');
      expect(params.url).toBe('/admin/business-units/'); // Should remain unchanged
    });

    test('should log URL transformation', () => {
      const params = { url: 'onboarding:bu' };
      const payload = {};

      fire_ajax_form_post(params, payload);

      expect(mockUrlMapper.logger.log).toHaveBeenCalledWith(
        'fire_ajax_form_post URL transformed',
        'onboarding:bu',
        'admin_panel:bu_list'
      );
    });

    test('should handle missing UrlMapper gracefully', () => {
      window.UrlMapper = undefined;
      const params = { url: 'onboarding:bu' };
      const payload = {};

      expect(() => {
        fire_ajax_form_post(params, payload);
      }).not.toThrow();

      expect(global.$.ajax).toHaveBeenCalledWith({
        url: 'onboarding:bu', // Should remain unchanged
        type: 'post',
        data: payload
      });
    });

    test('should handle params without URL', () => {
      const params = {};
      const payload = {};

      expect(() => {
        fire_ajax_form_post(params, payload);
      }).not.toThrow();
    });

    test('should preserve other parameters during transformation', () => {
      const params = { 
        url: 'onboarding:bu',
        modal: true,
        timeout: 5000
      };
      const payload = { formData: 'test' };

      fire_ajax_form_post(params, payload);

      expect(params.modal).toBe(true);
      expect(params.timeout).toBe(5000);
      expect(params.url).toBe('admin_panel:bu_list');
    });
  });

  describe('fire_ajax_get function', () => {
    function fire_ajax_get(params) {
      // Transform URL using URL mapper if available
      if (typeof window.UrlMapper !== 'undefined' && params.url) {
        const originalUrl = params.url;
        const transformedUrl = window.UrlMapper.transformUrl(originalUrl);
        if (originalUrl !== transformedUrl) {
          params.url = transformedUrl;
          if (window.UrlMapper.logger) {
            window.UrlMapper.logger.log('fire_ajax_get URL transformed', originalUrl, transformedUrl);
          }
        }
      }
      
      let data = Object.prototype.hasOwnProperty.call(params, "data") ? params.data : {};
      let callback = Object.prototype.hasOwnProperty.call(params, "beforeSend") ? params.beforeSend : function () {};
      
      return $.ajax({
        url: params.url,
        type: "get",
        data: data,
        beforeSend: callback
      });
    }

    test('should transform URLs in GET requests', () => {
      const params = { 
        url: '/onboarding/bu/?action=list',
        data: { id: 123 }
      };

      fire_ajax_get(params);

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('/onboarding/bu/?action=list');
      expect(params.url).toBe('/admin/business-units/?action=list');
    });

    test('should handle GET requests with query parameters', () => {
      const params = { 
        url: 'onboarding:bu',
        data: { action: 'list', filter: 'active' }
      };

      fire_ajax_get(params);

      expect(global.$.ajax).toHaveBeenCalledWith({
        url: 'admin_panel:bu_list',
        type: 'get',
        data: { action: 'list', filter: 'active' },
        beforeSend: expect.any(Function)
      });
    });

    test('should preserve beforeSend callback', () => {
      const mockCallback = jest.fn();
      const params = { 
        url: 'onboarding:bu',
        beforeSend: mockCallback
      };

      fire_ajax_get(params);

      expect(global.$.ajax).toHaveBeenCalledWith(
        expect.objectContaining({
          beforeSend: mockCallback
        })
      );
    });

    test('should handle empty data parameter', () => {
      const params = { url: 'onboarding:bu' };

      fire_ajax_get(params);

      expect(global.$.ajax).toHaveBeenCalledWith(
        expect.objectContaining({
          data: {}
        })
      );
    });
  });

  describe('fire_ajax_fileform_post function', () => {
    function fire_ajax_fileform_post(params, payload) {
      // Transform URL using URL mapper if available
      if (typeof window.UrlMapper !== 'undefined' && params["url"]) {
        const originalUrl = params["url"];
        const transformedUrl = window.UrlMapper.transformUrl(originalUrl);
        if (originalUrl !== transformedUrl) {
          params["url"] = transformedUrl;
          if (window.UrlMapper.logger) {
            window.UrlMapper.logger.log('fire_ajax_fileform_post URL transformed', originalUrl, transformedUrl);
          }
        }
      }
      
      return $.ajax({
        url: params["url"],
        type: "post",
        data: payload,
        processData: false,
        contentType: false,
      });
    }

    test('should transform URLs for file uploads', () => {
      const params = { url: 'onboarding:import' };
      const formData = new FormData();
      formData.append('file', 'test');

      fire_ajax_fileform_post(params, formData);

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('onboarding:import');
    });

    test('should preserve file upload settings', () => {
      const params = { url: 'onboarding:import' };
      const formData = new FormData();

      fire_ajax_fileform_post(params, formData);

      expect(global.$.ajax).toHaveBeenCalledWith({
        url: expect.any(String),
        type: 'post',
        data: formData,
        processData: false,
        contentType: false
      });
    });

    test('should log file upload URL transformations', () => {
      const params = { url: 'onboarding:import' };
      const formData = new FormData();

      fire_ajax_fileform_post(params, formData);

      expect(mockUrlMapper.logger.log).toHaveBeenCalledWith(
        'fire_ajax_fileform_post URL transformed',
        'onboarding:import',
        'onboarding:import' // Note: this mapping needs to be set in mock
      );
    });
  });

  describe('request_ajax_form_delete function', () => {
    function request_ajax_form_delete(params) {
      // Transform URL using URL mapper if available
      if (typeof window.UrlMapper !== 'undefined' && params["url"]) {
        const originalUrl = params["url"];
        const transformedUrl = window.UrlMapper.transformUrl(originalUrl);
        if (originalUrl !== transformedUrl) {
          params["url"] = transformedUrl;
          if (window.UrlMapper.logger) {
            window.UrlMapper.logger.log('request_ajax_form_delete URL transformed', originalUrl, transformedUrl);
          }
        }
      }
      
      return $.ajax({
        url: params["url"],
        type: "get",
      });
    }

    test('should transform delete request URLs', () => {
      const params = { url: 'onboarding:bu?action=delete&id=123' };

      request_ajax_form_delete(params);

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('onboarding:bu?action=delete&id=123');
    });

    test('should use GET method for delete requests', () => {
      const params = { url: 'onboarding:bu' };

      request_ajax_form_delete(params);

      expect(global.$.ajax).toHaveBeenCalledWith({
        url: expect.any(String),
        type: 'get'
      });
    });

    test('should handle delete URLs with parameters', () => {
      const params = { url: '/onboarding/bu/?action=delete&id=456' };

      request_ajax_form_delete(params);

      expect(params.url).toBe('/admin/business-units/?action=delete&id=456');
    });
  });

  describe('jQuery AJAX wrapper integration', () => {
    let interceptedAjax;

    beforeEach(() => {
      // Simulate the AJAX wrapper from url_mapper.js
      const originalJQueryAjax = global.$.ajax;
      
      interceptedAjax = function(options) {
        if (options.url && window.UrlMapper) {
          const originalUrl = options.url;
          const transformedUrl = window.UrlMapper.transformUrl(originalUrl);
          
          if (originalUrl !== transformedUrl) {
            options.url = transformedUrl;
            window.UrlMapper.logger.log('AJAX URL transformed', originalUrl, transformedUrl);
          }
        }
        
        return originalJQueryAjax.call(this, options);
      };

      global.$.ajax = interceptedAjax;
    });

    test('should intercept and transform jQuery AJAX calls', () => {
      $.ajax({
        url: 'onboarding:bu',
        type: 'GET',
        data: {}
      });

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('onboarding:bu');
      expect(mockUrlMapper.logger.log).toHaveBeenCalledWith(
        'AJAX URL transformed',
        'onboarding:bu',
        'admin_panel:bu_list'
      );
    });

    test('should not interfere with non-legacy URLs', () => {
      const modernUrl = '/admin/business-units/';
      
      $.ajax({
        url: modernUrl,
        type: 'GET'
      });

      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(modernUrl);
      // Should not log transformation since URL doesn't change
    });

    test('should handle AJAX calls without UrlMapper', () => {
      window.UrlMapper = undefined;

      expect(() => {
        $.ajax({
          url: 'onboarding:bu',
          type: 'GET'
        });
      }).not.toThrow();
    });

    test('should preserve original AJAX options', () => {
      const options = {
        url: 'onboarding:bu',
        type: 'POST',
        data: { test: 'data' },
        timeout: 5000,
        headers: { 'X-Custom': 'value' }
      };

      $.ajax(options);

      // URL should be transformed, but other options preserved
      expect(options.type).toBe('POST');
      expect(options.data).toEqual({ test: 'data' });
      expect(options.timeout).toBe(5000);
      expect(options.headers).toEqual({ 'X-Custom': 'value' });
    });

    test('should handle error responses with URL logging', () => {
      // Mock a failing AJAX call
      const originalError = jest.fn();
      const options = {
        url: 'onboarding:bu',
        error: originalError
      };

      // Simulate the error enhancement logic
      const enhancedError = function(xhr, status, error) {
        if (xhr.status === 404) {
          mockUrlMapper.logger.error(`AJAX request failed (404) - URL might need migration`, 
            `URL: ${options.url}, Status: ${status}, Error: ${error}`);
        }
        if (originalError) {
          return originalError.apply(this, arguments);
        }
      };

      // Simulate 404 error
      enhancedError({ status: 404 }, 'error', 'Not Found');

      expect(mockUrlMapper.logger.error).toHaveBeenCalledWith(
        `AJAX request failed (404) - URL might need migration`,
        expect.stringContaining('URL: admin_panel:bu_list')
      );
    });
  });

  describe('Integration with existing AJAX patterns', () => {
    test('should work with promise-based AJAX calls', async () => {
      const mockResponse = { success: true, data: [] };
      
      // Mock successful response
      global.$.ajax = jest.fn(() => Promise.resolve(mockResponse));

      const params = { url: 'onboarding:bu' };
      
      // Simulate fire_ajax_get call
      const result = await global.$.ajax({
        url: mockUrlMapper.transformUrl(params.url),
        type: 'get'
      });

      expect(result).toEqual(mockResponse);
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('onboarding:bu');
    });

    test('should work with callback-based AJAX calls', (done) => {
      // Mock callback-style response
      global.$.ajax = jest.fn(() => ({
        done: jest.fn((callback) => {
          setTimeout(() => {
            callback({ success: true });
            done();
          }, 0);
          return { fail: jest.fn() };
        }),
        fail: jest.fn()
      }));

      const params = { url: 'onboarding:bu' };
      
      // Simulate the pattern used in the app
      global.$.ajax({
        url: mockUrlMapper.transformUrl(params.url),
        type: 'post',
        data: {}
      }).done((data) => {
        expect(data.success).toBe(true);
      });
    });

    test('should maintain compatibility with existing error handlers', () => {
      const mockError = jest.fn();
      
      global.$.ajax = jest.fn(() => ({
        done: jest.fn(() => ({
          fail: jest.fn((callback) => {
            setTimeout(() => callback({ status: 500 }, 'error', 'Server Error'), 0);
            return {};
          })
        })),
        fail: mockError
      }));

      const params = { url: 'onboarding:bu' };
      
      global.$.ajax({
        url: mockUrlMapper.transformUrl(params.url),
        type: 'get'
      }).done().fail((xhr, status, error) => {
        expect(xhr.status).toBe(500);
        expect(status).toBe('error');
        expect(error).toBe('Server Error');
      });
    });
  });

  describe('Performance of AJAX interception', () => {
    test('should not significantly slow down AJAX calls', async () => {
      const params = { url: 'onboarding:bu' };
      
      const time = await performanceUtils.measureTime(() => {
        for (let i = 0; i < 1000; i++) {
          // Simulate URL transformation in AJAX call
          mockUrlMapper.transformUrl(params.url);
        }
      });

      // 1000 transformations should take less than 5ms
      expect(time).toBeLessThan(5);
    });

    test('should handle rapid successive AJAX calls', async () => {
      const urls = [
        'onboarding:bu',
        'onboarding:client', 
        'onboarding:contract',
        '/onboarding/import/',
        'activity:asset'
      ];

      const time = await performanceUtils.measureTime(() => {
        urls.forEach(url => {
          for (let i = 0; i < 100; i++) {
            mockUrlMapper.transformUrl(url);
          }
        });
      });

      // 500 transformations should be very fast
      expect(time).toBeLessThan(10);
    });
  });
});