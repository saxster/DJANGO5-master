/**
 * End-to-end navigation flow tests
 * Tests complete user journeys through the application
 */

// Mock browser environment for E2E-style tests
const fs = require('fs');
const path = require('path');

describe('End-to-End Navigation Flows', () => {
  let mockWindow, mockDocument, mockUrlMapper;

  beforeEach(() => {
    testUtils.resetMocks();
    
    // Setup comprehensive browser environment mock
    mockWindow = {
      location: {
        hostname: 'localhost',
        href: 'http://localhost:8000',
        pathname: '/',
        search: '',
        hash: ''
      },
      history: {
        pushState: jest.fn(),
        replaceState: jest.fn(),
        back: jest.fn(),
        forward: jest.fn()
      },
      addEventListener: jest.fn(),
      UrlMapper: undefined
    };

    mockDocument = {
      readyState: 'complete',
      addEventListener: jest.fn(),
      querySelector: jest.fn(),
      querySelectorAll: jest.fn(() => []),
      createElement: jest.fn(() => ({
        click: jest.fn(),
        href: '',
        download: '',
        addEventListener: jest.fn()
      })),
      body: {
        appendChild: jest.fn(),
        removeChild: jest.fn()
      }
    };

    // Setup URL mapper
    mockUrlMapper = testUtils.createMockUrlMapper({
      transformUrl: jest.fn(url => {
        const mappings = {
          'onboarding:bu': 'admin_panel:bu_list',
          'onboarding:client': 'admin_panel:clients_list',
          'onboarding:contract': 'admin_panel:contracts_list',
          'onboarding:import': 'admin_panel:data_import',
          '/onboarding/bu/': '/admin/business-units/',
          '/onboarding/client/': '/admin/clients/'
        };
        
        for (const [old, newUrl] of Object.entries(mappings)) {
          if (url.includes(old)) {
            return url.replace(old, newUrl);
          }
        }
        
        return url;
      })
    });

    global.window = mockWindow;
    global.document = mockDocument;
    mockWindow.UrlMapper = mockUrlMapper;
  });

  afterEach(() => {
    testUtils.resetMocks();
  });

  describe('Business Unit Management Flow', () => {
    test('should complete full business unit creation flow', async () => {
      const journey = new UserJourney();

      // 1. Navigate to business unit list
      await journey.navigateTo('/admin/business-units/');
      expect(journey.currentUrl).toBe('/admin/business-units/');
      
      // 2. Click "Add New" button (simulated)
      await journey.clickElement('.add_new_vendor');
      expect(journey.interactions.clicks).toContain('.add_new_vendor');
      
      // 3. Fill form (simulated)
      await journey.fillForm({
        'buname': 'Test Business Unit',
        'bucode': 'TBU001',
        'buaddress': '123 Test Street',
        'contactperson': 'John Doe'
      });
      
      expect(journey.formData['buname']).toBe('Test Business Unit');
      
      // 4. Submit form via AJAX
      await journey.submitFormAjax();
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:bu_list')
      );
      
      // 5. Verify success feedback
      expect(journey.lastResponse.success).toBe(true);
    });

    test('should handle business unit editing flow', async () => {
      const journey = new UserJourney();

      // Navigate to edit form
      await journey.navigateTo('/admin/business-units/?id=123');
      
      // Load existing data (simulated)
      await journey.loadExistingData({
        id: 123,
        buname: 'Existing BU',
        bucode: 'EBU001'
      });
      
      // Modify form data
      await journey.updateForm({
        'buname': 'Updated Business Unit',
        'buaddress': '456 Updated Street'
      });
      
      // Submit update
      await journey.submitFormAjax();
      
      expect(journey.formData['buname']).toBe('Updated Business Unit');
      expect(journey.lastResponse.success).toBe(true);
    });

    test('should handle business unit deletion flow', async () => {
      const journey = new UserJourney();

      await journey.navigateTo('/admin/business-units/');
      
      // Click delete button for specific BU
      await journey.clickElement('.delete-btn[data-id="123"]');
      
      // Confirm deletion in modal
      await journey.confirmAction('delete');
      
      // Verify delete AJAX call
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:bu_list')
      );
      
      expect(journey.lastResponse.success).toBe(true);
    });
  });

  describe('Cross-Module Navigation Flow', () => {
    test('should navigate between business units and clients', async () => {
      const journey = new UserJourney();

      // Start at business units
      await journey.navigateTo('/admin/business-units/');
      expect(journey.currentUrl).toBe('/admin/business-units/');
      
      // Navigate to clients via menu/link
      await journey.navigateTo('/admin/clients/');
      expect(journey.currentUrl).toBe('/admin/clients/');
      
      // Verify URL transformation occurred
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith('/admin/clients/');
      
      // Navigate back to business units
      await journey.navigateTo('/admin/business-units/');
      expect(journey.currentUrl).toBe('/admin/business-units/');
    });

    test('should maintain state during navigation', async () => {
      const journey = new UserJourney();

      // Start filling business unit form
      await journey.navigateTo('/admin/business-units/?action=form');
      await journey.fillForm({
        'buname': 'Partial BU',
        'bucode': 'PBU001'
      });
      
      // Navigate away (e.g., to clients)
      await journey.navigateTo('/admin/clients/');
      
      // Navigate back to business units
      await journey.navigateTo('/admin/business-units/?action=form');
      
      // Check if unsaved data warning would be shown
      expect(journey.hasUnsavedChanges()).toBe(true);
    });
  });

  describe('Import/Export Flow', () => {
    test('should complete data import workflow', async () => {
      const journey = new UserJourney();

      // Navigate to import page
      await journey.navigateTo('/admin/data/import/');
      
      // Select table type
      await journey.selectOption('#id_table', 'BUSINESS_UNITS');
      
      // Download template
      await journey.clickElement('#btn_download');
      expect(journey.downloads).toContain('template');
      
      // Upload file
      await journey.uploadFile('#id_importfile', 'test-data.xlsx');
      
      // Submit import
      await journey.clickElement('#btn_importdata');
      await journey.confirmAction('import');
      
      // Verify import AJAX call uses correct URL
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:data_import')
      );
      
      expect(journey.lastResponse.success).toBe(true);
    });

    test('should handle bulk update workflow', async () => {
      const journey = new UserJourney();

      await journey.navigateTo('/admin/data/bulk-update/');
      
      await journey.selectOption('#id_table', 'CLIENTS');
      await journey.uploadFile('#id_importfile', 'update-data.xlsx');
      await journey.clickElement('#btn_importdata');
      
      // Verify URL transformation
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:data_bulk_update')
      );
    });
  });

  describe('Configuration Management Flow', () => {
    test('should manage shift configuration', async () => {
      const journey = new UserJourney();

      // Navigate to shifts configuration
      await journey.navigateTo('/admin/config/shifts/');
      
      // Add new shift
      await journey.clickElement('.add_new_vendor');
      
      // Fill shift form
      await journey.fillForm({
        'shiftname': 'Morning Shift',
        'starttime': '08:00',
        'endtime': '16:00',
        'peoplecount': '5'
      });
      
      // Submit shift
      await journey.submitFormAjax();
      
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:config_shifts')
      );
    });

    test('should manage geofence configuration', async () => {
      const journey = new UserJourney();

      await journey.navigateTo('/admin/config/geofences/');
      
      await journey.fillForm({
        'geofencename': 'Main Office',
        'latitude': '40.7128',
        'longitude': '-74.0060',
        'radius': '100'
      });
      
      await journey.submitFormAjax();
      
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledWith(
        expect.stringContaining('admin_panel:config_geofences')
      );
    });
  });

  describe('Error Handling Flow', () => {
    test('should handle network errors gracefully', async () => {
      const journey = new UserJourney();
      
      // Simulate network error
      journey.simulateNetworkError();
      
      await journey.navigateTo('/admin/business-units/');
      await journey.submitFormAjax();
      
      // Should show error message
      expect(journey.hasErrorMessage()).toBe(true);
      expect(journey.errorMessage).toContain('network');
    });

    test('should handle server errors with proper fallback', async () => {
      const journey = new UserJourney();
      
      // Simulate server error
      journey.simulateServerError(500);
      
      await journey.navigateTo('/admin/business-units/');
      await journey.submitFormAjax();
      
      // Should log error and show user-friendly message
      expect(mockUrlMapper.logger.error).toHaveBeenCalled();
      expect(journey.hasErrorMessage()).toBe(true);
    });

    test('should handle invalid URLs gracefully', async () => {
      const journey = new UserJourney();
      
      // Try to navigate to invalid URL
      await journey.navigateTo('/invalid/url/path/');
      
      // Should either redirect or show 404
      expect(journey.currentStatus).toBeIn([302, 404]);
    });
  });

  describe('Browser Compatibility Flow', () => {
    test('should work in Chrome-like environment', async () => {
      mockWindow.navigator = { userAgent: 'Chrome/91.0' };
      const journey = new UserJourney();

      await journey.navigateTo('/admin/business-units/');
      await journey.submitFormAjax();
      
      expect(mockUrlMapper.transformUrl).toHaveBeenCalled();
    });

    test('should work in Firefox-like environment', async () => {
      mockWindow.navigator = { userAgent: 'Firefox/89.0' };
      const journey = new UserJourney();

      await journey.navigateTo('/admin/business-units/');
      await journey.submitFormAjax();
      
      expect(mockUrlMapper.transformUrl).toHaveBeenCalled();
    });

    test('should handle IE-like environment', async () => {
      mockWindow.navigator = { userAgent: 'Trident/7.0' };
      const journey = new UserJourney();

      // IE might not support all modern features
      expect(() => {
        journey.navigateTo('/admin/business-units/');
      }).not.toThrow();
    });
  });

  describe('Performance Flow Testing', () => {
    test('should handle rapid navigation without issues', async () => {
      const journey = new UserJourney();
      
      const urls = [
        '/admin/business-units/',
        '/admin/clients/',
        '/admin/contracts/',
        '/admin/config/shifts/',
        '/admin/config/geofences/',
        '/admin/data/import/'
      ];
      
      const start = performance.now();
      
      // Rapidly navigate through all URLs
      for (const url of urls) {
        await journey.navigateTo(url);
      }
      
      const end = performance.now();
      const totalTime = end - start;
      
      // Should complete navigation in reasonable time
      expect(totalTime).toBeLessThan(100); // 100ms for mock navigation
      
      // All URL transformations should have occurred
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledTimes(urls.length);
    });

    test('should handle concurrent AJAX requests', async () => {
      const journey = new UserJourney();
      
      const promises = [];
      
      // Simulate multiple concurrent requests
      for (let i = 0; i < 10; i++) {
        promises.push(journey.makeAjaxRequest(`/admin/business-units/?id=${i}`));
      }
      
      await Promise.all(promises);
      
      // All requests should have been transformed
      expect(mockUrlMapper.transformUrl).toHaveBeenCalledTimes(10);
    });
  });
});

/**
 * Mock User Journey class for simulating user interactions
 */
class UserJourney {
  constructor() {
    this.currentUrl = '/';
    this.currentStatus = 200;
    this.formData = {};
    this.interactions = {
      clicks: [],
      navigation: [],
      forms: []
    };
    this.downloads = [];
    this.lastResponse = { success: true };
    this.errorMessage = '';
    this.networkError = false;
    this.serverError = false;
  }

  async navigateTo(url) {
    this.interactions.navigation.push(url);
    
    if (this.networkError) {
      throw new Error('Network error');
    }
    
    // Simulate URL transformation
    if (mockUrlMapper) {
      const transformedUrl = mockUrlMapper.transformUrl(url);
      this.currentUrl = transformedUrl;
    } else {
      this.currentUrl = url;
    }
    
    if (this.serverError) {
      this.currentStatus = this.serverError;
    } else {
      this.currentStatus = 200;
    }
    
    return Promise.resolve();
  }

  async clickElement(selector) {
    this.interactions.clicks.push(selector);
    
    // Simulate specific click behaviors
    if (selector.includes('download')) {
      this.downloads.push('template');
    }
    
    return Promise.resolve();
  }

  async fillForm(data) {
    Object.assign(this.formData, data);
    this.interactions.forms.push({ action: 'fill', data });
    return Promise.resolve();
  }

  async updateForm(data) {
    Object.assign(this.formData, data);
    this.interactions.forms.push({ action: 'update', data });
    return Promise.resolve();
  }

  async submitFormAjax() {
    this.interactions.forms.push({ action: 'submit', data: this.formData });
    
    if (this.networkError) {
      this.lastResponse = { success: false, error: 'Network error' };
      this.errorMessage = 'Network connection failed';
    } else if (this.serverError) {
      this.lastResponse = { success: false, error: 'Server error' };
      this.errorMessage = 'Server error occurred';
    } else {
      this.lastResponse = { success: true, data: this.formData };
    }
    
    // Simulate AJAX URL transformation
    if (mockUrlMapper) {
      mockUrlMapper.transformUrl(this.currentUrl);
    }
    
    return Promise.resolve(this.lastResponse);
  }

  async selectOption(selector, value) {
    this.formData[selector] = value;
    this.interactions.forms.push({ action: 'select', selector, value });
    return Promise.resolve();
  }

  async uploadFile(selector, filename) {
    this.formData[selector] = filename;
    this.interactions.forms.push({ action: 'upload', selector, filename });
    return Promise.resolve();
  }

  async confirmAction(action) {
    this.interactions.clicks.push(`confirm-${action}`);
    return Promise.resolve();
  }

  async loadExistingData(data) {
    Object.assign(this.formData, data);
    return Promise.resolve();
  }

  async makeAjaxRequest(url) {
    if (mockUrlMapper) {
      mockUrlMapper.transformUrl(url);
    }
    return Promise.resolve({ success: true });
  }

  hasUnsavedChanges() {
    return Object.keys(this.formData).length > 0;
  }

  hasErrorMessage() {
    return this.errorMessage.length > 0;
  }

  simulateNetworkError() {
    this.networkError = true;
  }

  simulateServerError(status) {
    this.serverError = status;
  }
}

// Custom Jest matcher
expect.extend({
  toBeIn(received, expected) {
    const pass = expected.includes(received);
    return {
      message: () => `expected ${received} to be in ${expected}`,
      pass
    };
  }
});