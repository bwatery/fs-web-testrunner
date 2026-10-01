// =========================================================================
// Global Application State (Single Source of Truth)
// =========================================================================

// Test Cases & Execution State
let allTestCases = [];
let currentFilter = 'all';
let stats = { total: 0, executed: 0, passed: 0, failed: 0 };
let ws = null;
let selectedCaseIds = new Set();
let currentDisplayedTests = [];

// HIS Validator & Identity Switcher State
let liveValidatorData = null;
let validatorPollInterval = null;
let cachedOrderItems = [];

// Business Rules Center State
let allBusinessRules = [];
let currentRuleFilter = 'all';
let ruleSearchQuery = '';
let currentRuleView = 'groups';
let currentRuleDomain = 'all';
let currentRuleSeverity = 'all';
