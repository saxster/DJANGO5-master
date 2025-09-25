/**
 * Jest setup file for frontend URL mapping tests
 * Provides mocks and global utilities for testing
 */

// Mock jQuery for tests
global.$ = global.jQuery = {
  ajax: jest.fn(() => ({
    done: jest.fn(() => ({
      fail: jest.fn(() => ({}))
    })),
    fail: jest.fn(() => ({}))
  })),
  extend: jest.fn((target, ...sources) => Object.assign(target, ...sources)),
  param: jest.fn(obj => new URLSearchParams(obj).toString())
};

// Mock console methods for testing
global.console = {
  ...console,
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn()
};

// Mock window object
Object.defineProperty(window, 'location', {
  value: {
    hostname: 'localhost',
    href: 'http://localhost:8000',
    search: '',
    pathname: '/'
  },
  writable: true
});

// Mock document methods
Object.defineProperty(document, 'readyState', {
  value: 'complete',
  writable: true
});

// Mock DOM event handling
document.addEventListener = jest.fn();
document.createElement = jest.fn(() => ({
  click: jest.fn(),
  href: '',
  download: ''
}));

// Mock URL object for tests
global.URL = {
  createObjectURL: jest.fn(() => 'mock-blob-url')
};

// Mock XMLHttpRequest for AJAX testing
class MockXMLHttpRequest {
  constructor() {
    this.readyState = 0;
    this.status = 200;
    this.responseText = '';
    this.responseJSON = {};
  }
  
  open(method, url) {
    this.method = method;
    this.url = url;
  }
  
  send(data) {
    this.data = data;
    setTimeout(() => {
      this.readyState = 4;
      if (this.onreadystatechange) {
        this.onreadystatechange();
      }
    }, 0);
  }
  
  setRequestHeader(header, value) {
    this.headers = this.headers || {};
    this.headers[header] = value;
  }
}

global.XMLHttpRequest = MockXMLHttpRequest;

// Test utilities
global.testUtils = {
  /**
   * Create a mock request object for testing
   */
  createMockRequest: (overrides = {}) => ({
    url: '/test/url/',
    method: 'GET',
    data: {},
    headers: {},
    ...overrides
  }),

  /**
   * Create a mock UrlMapper for testing
   */
  createMockUrlMapper: (overrides = {}) => ({
    transformUrl: jest.fn(url => url),
    isLegacyUrl: jest.fn(() => false),
    mapNamespace: jest.fn(namespace => namespace),
    logger: {
      log: jest.fn(),
      warn: jest.fn(),
      error: jest.fn()
    },
    URL_NAMESPACE_MAPPINGS: {
      'onboarding:bu': 'admin_panel:bu_list',
      'onboarding:client': 'admin_panel:clients_list'
    },
    PATH_PATTERN_MAPPINGS: {
      '/onboarding/bu/': '/admin/business-units/',
      '/onboarding/client/': '/admin/clients/'
    },
    ...overrides
  }),

  /**
   * Reset all mocks
   */
  resetMocks: () => {
    jest.clearAllMocks();
    console.log.mockClear();
    console.warn.mockClear();
    console.error.mockClear();
  },

  /**
   * Create a delay for async testing
   */
  delay: (ms = 0) => new Promise(resolve => setTimeout(resolve, ms)),

  /**
   * Assert that a function was called with specific arguments
   */
  expectCalledWith: (mockFn, ...args) => {
    expect(mockFn).toHaveBeenCalledWith(...args);
  },

  /**
   * Assert console logging occurred
   */
  expectConsoleLog: (message) => {
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining(message)
    );
  },

  /**
   * Assert console warning occurred  
   */
  expectConsoleWarn: (message) => {
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining(message)
    );
  }
};

// Performance testing utilities
global.performanceUtils = {
  /**
   * Measure execution time of a function
   */
  measureTime: async (fn) => {
    const start = performance.now();
    await fn();
    const end = performance.now();
    return end - start;
  },

  /**
   * Run a function multiple times and get average execution time
   */
  measureAverageTime: async (fn, iterations = 100) => {
    const times = [];
    for (let i = 0; i < iterations; i++) {
      times.push(await performanceUtils.measureTime(fn));
    }
    return times.reduce((sum, time) => sum + time, 0) / times.length;
  },

  /**
   * Assert that execution time is below threshold
   */
  expectFasterThan: async (fn, maxTime) => {
    const time = await performanceUtils.measureTime(fn);
    expect(time).toBeLessThan(maxTime);
  }
};