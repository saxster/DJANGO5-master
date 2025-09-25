#!/usr/bin/env node
/**
 * Direct test of URL mapper functionality
 * Validates core transformations without Jest overhead
 */

const fs = require('fs');

// Create a minimal DOM/window environment
global.window = {
    URL_DEBUG_MODE: false, // Disable debug mode to avoid XMLHttpRequest issues
    location: { hostname: 'localhost' }
};
global.document = {
    readyState: 'complete',
    addEventListener: () => {}
};

// Mock XMLHttpRequest for Node.js
global.XMLHttpRequest = function() {};
global.XMLHttpRequest.prototype = {
    open: function() {},
    send: function() {},
    setRequestHeader: function() {}
};

// Load the URL mapper
const urlMapperCode = fs.readFileSync('frontend/static/assets/js/local/url_mapper.js', 'utf8');
eval(urlMapperCode);

// Test core functionality
console.log('=== URL Mapper Direct Validation ===\n');

// Test 1: Core transformations
console.log('1. Core URL Transformations:');
const testMappings = [
    ['onboarding:bu', 'admin_panel:bu_list'],
    ['onboarding:client', 'admin_panel:clients_list'],
    ['onboarding:contract', 'admin_panel:contracts_list'],
    ['onboarding:import', 'admin_panel:data_import'],
    ['onboarding:shift', 'admin_panel:config_shifts'],
    ['/onboarding/bu/', '/admin/business-units/'],
    ['/onboarding/client/', '/admin/clients/']
];

let passed = 0, failed = 0;

testMappings.forEach(([input, expected]) => {
    const result = window.UrlMapper.transformUrl(input);
    const success = result === expected;
    console.log(`   ${input} -> ${result} ${success ? '✅' : '❌'}`);
    if (success) passed++; else failed++;
    if (!success) console.log(`      Expected: ${expected}`);
});

console.log(`\n   Results: ${passed} passed, ${failed} failed\n`);

// Test 2: Legacy URL detection
console.log('2. Legacy URL Detection:');
const legacyTests = [
    ['onboarding:bu', true],
    ['onboarding:client', true],
    ['admin_panel:bu_list', false],
    ['/modern/url/', false]
];

legacyTests.forEach(([input, expected]) => {
    const result = window.UrlMapper.isLegacyUrl(input);
    const success = result === expected;
    console.log(`   ${input} -> ${result ? 'legacy' : 'modern'} ${success ? '✅' : '❌'}`);
});

// Test 3: Edge cases
console.log('\n3. Edge Case Handling:');
const edgeCases = [
    [null, null],
    [undefined, undefined],
    ['', ''],
    ['unknown:namespace', 'unknown:namespace']
];

edgeCases.forEach(([input, expected]) => {
    try {
        const result = window.UrlMapper.transformUrl(input);
        const success = result === expected;
        console.log(`   ${input || 'null/undefined'} -> ${result || 'null/undefined'} ${success ? '✅' : '❌'}`);
    } catch (e) {
        console.log(`   ${input || 'null/undefined'} -> ERROR: ${e.message} ❌`);
    }
});

// Test 4: Performance check
console.log('\n4. Performance Test:');
const perfTest = () => {
    const iterations = 1000;
    const start = process.hrtime.bigint();
    
    for (let i = 0; i < iterations; i++) {
        window.UrlMapper.transformUrl('onboarding:bu');
        window.UrlMapper.transformUrl('onboarding:client');
        window.UrlMapper.transformUrl('/onboarding/contract/');
    }
    
    const end = process.hrtime.bigint();
    const totalTime = Number(end - start) / 1000000; // Convert to milliseconds
    const avgTime = totalTime / (iterations * 3);
    
    console.log(`   ${iterations * 3} transformations in ${totalTime.toFixed(2)}ms`);
    console.log(`   Average: ${avgTime.toFixed(4)}ms per transformation`);
    console.log(`   Performance: ${avgTime < 1 ? '✅ Fast' : '❌ Slow'}`);
    
    return avgTime;
};

const avgTime = perfTest();

// Test 5: Mapping completeness
console.log('\n5. Mapping Completeness:');
const mappingCount = Object.keys(window.UrlMapper.URL_NAMESPACE_MAPPINGS).length;
const pathMappingCount = Object.keys(window.UrlMapper.PATH_PATTERN_MAPPINGS).length;
console.log(`   Namespace mappings: ${mappingCount}`);
console.log(`   Path mappings: ${pathMappingCount}`);
console.log(`   Total mappings: ${mappingCount + pathMappingCount}`);
console.log(`   Completeness: ${mappingCount >= 70 ? '✅ Comprehensive' : '⚠️  May need more mappings'}`);

// Summary
console.log('\n=== Validation Summary ===');
console.log(`✅ JavaScript syntax: Valid`);
console.log(`${failed === 0 ? '✅' : '❌'} Core transformations: ${passed}/${passed + failed} passed`);
console.log(`${avgTime < 1 ? '✅' : '❌'} Performance: ${avgTime.toFixed(4)}ms avg`);
console.log(`${mappingCount >= 70 ? '✅' : '⚠️ '} Mapping count: ${mappingCount} namespace mappings`);

if (failed === 0 && avgTime < 1) {
    console.log('\n🎉 URL Mapper validation PASSED - Ready for deployment!');
    process.exit(0);
} else {
    console.log('\n❌ URL Mapper validation FAILED - Issues need to be addressed');
    process.exit(1);
}