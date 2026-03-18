# DSL Reference

**Modern Trigger DSL Syntax Guide**

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Core Syntax](#core-syntax)
  - [State Accessors](#state-accessors)
  - [Tag Accessors](#tag-accessors)
  - [Event Accessors](#event-accessors)
- [Advanced Features](#advanced-features)
  - [Boolean Shorthand](#boolean-shorthand)
  - [EXISTS Operator](#exists-operator)
  - [IN Operator](#in-operator)
  - [String Operations](#string-operations)
  - [COUNT with WHERE](#count-with-where)
- [Operators](#operators)
- [Duration Format](#duration-format)
- [Complete Examples](#complete-examples)

## Overview

The AMI Trigger DSL uses intuitive **dot notation** for defining when EMUs should fire. It provides:

- **Type-safe operations** on state atoms
- **Temporal queries** on event history
- **Attribute filtering** with WHERE clauses
- **Logical composition** with AND, OR, NOT

**Key principle**: DSL expressions are **deterministic** - same inputs always produce same outputs.

## Quick Start

```javascript
// Simple state check
state.user.tier == 'premium'

// Event counting with filtering (ergonomic syntax - recommended)
COUNT event.user.clicked.button WHERE user_id == '12345' IN 'PT1H' > 5

// Complex rule
state.user.tier IN ['gold', 'platinum'] AND
state.account.verified AND
COUNT event.order.placed WHERE customer_id == 'cust-123' IN 'P30D' >= 3
```

## Core Syntax

### State Accessors

Check state atom values using **dot notation**.

**Syntax**:
```javascript
state.namespace.key OPERATOR value
```

**Examples**:

```javascript
// Value comparisons
state.user.tier == 'premium'
state.user.age >= 18
state.order.total > 100.00
state.sentiment.score < 0.4

// All comparison operators
state.ticket.priority != 'low'
state.user.balance >= 1000
state.system.cpu_usage > 85
state.score <= 0.5
```

**Type rules**:
- **Equality** (`==`, `!=`): Works with any types
- **Comparison** (`>`, `>=`, `<`, `<=`): Requires **numeric** types

**Validation**:

```javascript
// ✅ Valid
state.user.tier == 'premium'
state.order.total >= 1000

// ❌ Invalid - uppercase key
state.User.Tier == 'premium'

// ❌ Invalid - single segment
state.tier == 'premium'  // Must be state.namespace.tier

// ❌ Invalid - string comparison with numeric operators
state.user.name > 'alice'  // Use string operations instead
```

### Tag Accessors

Check tag atom values (exact match).

**Syntax**:
```javascript
tag.kind OPERATOR value
```

**Examples**:

```javascript
// Basic tags
tag.priority == 'high'
tag.channel == 'email'
tag.language == 'spanish'

// Sentiment/intent tags
tag.sentiment == 'negative'
tag.intent == 'upgrade_request'

// Department/category tags
tag.department == 'engineering'
tag.category == 'billing_issue'
```

**Normalization**: Both kind and value are normalized (NFKC Unicode + casefold).

```javascript
// These are equivalent after normalization:
tag.Priority == 'HIGH'
tag.priority == 'high'
tag.PRIORITY == 'High'
```

### Event Accessors

Check if events occurred and count them.

**Syntax**:
```javascript
// Simple event check
event.subject.verb.object

// Event recency
event.subject.verb.object IN 'duration'

// Event with attribute filtering (NEW!)
event.subject.verb.object WHERE attr == value IN 'duration'

// Cross-project event check (4-part notation)
event.project_name.subject.verb.object IN 'duration'

// Event counting (ergonomic syntax - recommended)
COUNT event.subject.verb.object IN 'duration' OPERATOR number

// Event counting with filtering (ergonomic syntax - recommended)
COUNT event.subject.verb.object WHERE attr == value IN 'duration' OPERATOR number

// Event counting (original syntax - also supported)
COUNT(event.subject.verb.object IN 'duration') OPERATOR number
COUNT(event.subject.verb.object WHERE attr == value IN 'duration') OPERATOR number
```

**Examples**:

```javascript
// Basic event checks (current project)
event.user.logged.in
event.order.placed.cart
event.agent.sent.email

// Cross-project event checks (4-part notation)
event.auth_service.user.logged.in IN 'PT1H'      // Events from auth_service project
event.support_proj.agent.escalated.case IN 'P7D' // Events from support_proj project

// Event recency
event.user.failed.login IN 'PT15M'        // Within last 15 minutes
event.customer.completed.purchase IN 'P7D'  // Within last 7 days

// Event with attribute filtering (check if SPECIFIC user/entity did something)
event.user.failed.login WHERE user_id == '12345' IN 'PT15M'
event.order.shipped WHERE order_id == 'ord-456' IN 'P7D'
event.session.expired WHERE session_id == 'sess-789' IN 'PT1H'

// Simple counting (ergonomic syntax)
COUNT event.user.clicked.button IN 'PT1H' > 5
COUNT event.order.placed IN 'P30D' >= 10

// Cross-project counting
COUNT event.analytics_proj.user.viewed.page IN 'P7D' >= 50

// Counting with WHERE clause (see Advanced Features)
COUNT event.user.clicked.button WHERE user_id == '12345' IN 'PT1H' > 5
```

**Cross-Project Event Queries**:

The DSL supports querying events from other projects within the same workspace using **4-part notation**:

```javascript
// Format: event.PROJECT_NAME.subject.verb.object IN 'duration'
event.project_a.user.clicked.button IN 'PT1H'
event.project_b.agent.sent.email IN 'P7D'
```

This enables:
- **Workspace-level coordination** between projects
- **Multi-service event correlation** (e.g., auth service + main app)
- **Cross-project dependencies** in trigger logic

**Example use cases**:

```javascript
// Require authentication before purchase
event.auth_service.user.logged.in IN 'PT24H' AND
event.shop_service.user.initiated.checkout

// Escalate support ticket if auth failed
event.auth_service.user.failed.login IN 'PT15M' AND
COUNT(event.auth_service.user.failed.login IN 'PT15M') >= 5

// Cross-service workflow tracking
event.api_gateway.request.received IN 'PT1H' AND
event.payment_service.payment.completed IN 'PT1H' AND
NOT event.notification_service.email.sent IN 'PT1H'
```

## Advanced Features

### Boolean Shorthand

Check boolean state without explicit `== true`.

**Examples**:

```javascript
// Shorthand
state.user.premium
state.user.verified AND state.account.active

// Equivalent to:
state.user.premium == true
state.user.verified == true AND state.account.active == true

// Negation
NOT state.user.banned  // Same as state.user.banned != true
```

**Truthiness rules**:
- Boolean `true` → true
- String `"true"`, `"yes"`, `"1"` → true (case-insensitive)
- Number > 0 → true
- Everything else → false

### EXISTS Operator

Check if a field exists and has a non-null value.

**Syntax**:
```javascript
state.namespace.key EXISTS
tag.kind EXISTS
```

**Examples**:

```javascript
// Check field presence
state.user.email EXISTS
state.optional.field EXISTS

// Common pattern: check existence before using
state.user.email EXISTS AND state.user.email ENDS_WITH '@company.com'

// Tags
tag.priority EXISTS
```

**Behavior**:
- Returns `false` if key doesn't exist
- Returns `false` if value is `null`
- Returns `true` if key exists with non-null value

### IN Operator

Check membership in a list of values.

**Syntax**:
```javascript
state.namespace.key IN [value1, value2, ...]
tag.kind IN [value1, value2, ...]
```

**Examples**:

```javascript
// State checks
state.user.role IN ['admin', 'moderator', 'owner']
state.user.country IN ['US', 'CA', 'MX']
state.tier IN ['gold', 'platinum', 'diamond']

// Tag checks
tag.priority IN ['high', 'critical']
tag.category IN ['billing', 'support', 'sales']

// Mixed types (numbers and strings)
state.status_code IN [200, 201, 204]
state.level IN [1, 2, 3]
```

**Normalization**: String values are case-insensitive and Unicode-normalized.

```javascript
// These all match:
state.role IN ['Admin', 'ADMIN', 'admin']
```

### String Operations

Perform pattern matching on string values.

**Operators**:
- `STARTS_WITH` - Check prefix
- `ENDS_WITH` - Check suffix
- `CONTAINS` - Check substring
- `MATCHES` - Regex pattern match

**Examples**:

```javascript
// Email validation
state.user.email ENDS_WITH '@company.com'
state.user.email STARTS_WITH 'admin-'

// Content filtering
state.message CONTAINS 'urgent'
state.subject CONTAINS 'ALERT'

// Pattern matching with regex
state.code MATCHES '^[A-Z]{3}-\d{4}$'
state.phone MATCHES '^\+1-\d{3}-\d{3}-\d{4}$'

// Name checks
state.user.name STARTS_WITH 'Dr.'
state.filename ENDS_WITH '.pdf'
```

**Notes**:
- All string operations are case-sensitive by default
- `MATCHES` uses Python regex syntax
- Values are converted to strings if needed

### Event WHERE Clause

Filter events by attribute values for existence checks (not just counting).

**Syntax**:
```javascript
event.subject.verb.object WHERE condition [AND condition...] IN 'duration'
```

**Key Difference from COUNT**:
- **Event WHERE**: Returns `true/false` if ANY matching event exists (short-circuits on first match)
- **COUNT WHERE**: Returns the count of ALL matching events (scans all)

**Examples**:

```javascript
// Check if specific user performed action
event.user.failed.login WHERE user_id == 'user-123' IN 'PT15M'
event.order.placed WHERE customer_id == 'cust-456' IN 'P7D'

// Multiple attribute filtering
event.order.shipped WHERE order_id == 'ord-789' AND carrier == 'fedex' IN 'P7D'

// Session tracking
event.session.expired WHERE session_id == 'sess-abc123' IN 'PT1H'

// Document collaboration
event.document.edited WHERE user_id == 'alice' AND document_id == 'doc-123' IN 'PT24H'
```

**WHERE clause rules**:
- Only `==` operator supported (equality checks)
- Multiple conditions joined with `AND`
- Attribute names must be identifiers (no dots)
- Values must be string literals (`'value'`), number literals, or **template literals** (`'{{context.key}}'`)
- **CRITICAL**: State references (`state.xxx.yyy`) are NOT supported as WHERE values — the API rejects them with "Invalid trigger DSL syntax". Use template literals instead: `WHERE entity_id == '{{entity.id}}'`

**Common Use Cases**:

```javascript
// Account security: Check if THIS user had failed login
event.user.failed.login WHERE user_id == 'user-123' IN 'PT15M'

// Order tracking: Check if THIS order was shipped
event.order.shipped WHERE order_id == 'ord-456' IN 'P7D'

// Session management: Check if THIS session expired
event.session.expired WHERE session_id == 'sess-789' IN 'PT1H'

// Multi-user systems: "Did MY user edit this document?"
// Use template literals to reference context values in WHERE clauses
event.document.edited WHERE user_id == '{{current_user.id}}' IN 'PT24H'

// Entity-scoped: "Was this entity's invite sent?"
event.staff.sent.invite WHERE entity_id == '{{entity.id}}' IN 'P3D'
```

**Performance Benefits**:
- Short-circuits on first match (faster than `COUNT >= 1`)
- More semantic: expresses intent ("did it happen?") vs counting

### COUNT with WHERE

Count events filtered by attribute values.

**Syntax (Ergonomic - Recommended)**:
```javascript
COUNT event.subject.verb.object WHERE condition [AND condition...] IN 'duration' OPERATOR number
```

**Syntax (Original - Also Supported)**:
```javascript
COUNT(event.subject.verb.object WHERE condition [AND condition...] IN 'duration') OPERATOR number
```

**Examples**:

```javascript
// Single condition (ergonomic syntax)
COUNT event.user.clicked.button WHERE user_id == '12345' IN 'PT1H' > 5
COUNT event.order.placed WHERE customer_id == 'cust-789' IN 'P7D' >= 3

// Multiple conditions (ergonomic syntax)
COUNT event.order.placed
  WHERE customer_id == 'cust-123' AND status == 'active'
  IN 'P7D' >= 10

// Numeric attributes (ergonomic syntax)
COUNT event.user.viewed.video WHERE duration == 120 IN 'P1D' > 5
COUNT event.purchase.completed WHERE amount >= 100 IN 'P30D' >= 3

// Original syntax (still works)
COUNT(event.user.clicked.button WHERE user_id == '12345' IN 'PT1H') > 5
```

**WHERE clause rules**:
- Only `==` operator supported (equality checks)
- Multiple conditions joined with `AND`
- Attribute names must be identifiers (no dots)
- Values must be string literals, number literals, or template literals (`'{{key}}'`)
- State references (`state.xxx`) are NOT valid WHERE values — use template literals

**Use cases**:

```javascript
// Account security (ergonomic syntax)
state.user.status == 'active' AND
COUNT event.user.failed.login
  WHERE user_id == 'user-123'
  IN 'PT15M' >= 5

// High-value customer detection
COUNT event.order.placed
  WHERE customer_id == 'cust-123' AND amount >= 1000
  IN 'P90D' >= 3

// Session activity tracking
COUNT event.user.clicked.button
  WHERE session_id == 'sess-456'
  IN 'PT1H' > 10
```

## Operators

### Comparison Operators

| Operator | Meaning | Numeric Only |
|----------|---------|--------------|
| `==` | Equal to | No |
| `!=` | Not equal to | No |
| `>` | Greater than | Yes |
| `>=` | Greater than or equal | Yes |
| `<` | Less than | Yes |
| `<=` | Less than or equal | Yes |

### Logical Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `AND` | Logical AND | `state.user.premium AND state.user.verified` |
| `OR` | Logical OR | `tag.priority == 'high' OR tag.priority == 'critical'` |
| `NOT` | Logical NOT | `NOT state.user.banned` |

**Precedence** (high to low):
1. `NOT`
2. `AND`
3. `OR`

**Grouping with parentheses**:

```javascript
(state.user.tier == 'premium' OR state.user.tier == 'enterprise')
AND state.account.verified
```

### Special Operators

| Operator | Purpose | Example |
|----------|---------|---------|
| `EXISTS` | Check field existence | `state.user.email EXISTS` |
| `IN` | List membership | `state.role IN ['admin', 'owner']` |
| `STARTS_WITH` | String prefix | `state.email STARTS_WITH 'admin-'` |
| `ENDS_WITH` | String suffix | `state.email ENDS_WITH '@company.com'` |
| `CONTAINS` | Substring check | `state.message CONTAINS 'urgent'` |
| `MATCHES` | Regex match | `state.code MATCHES '^[A-Z]{3}-\d{4}$'` |

## Duration Format

Use ISO 8601 duration strings for time windows.

### Common Durations

| Duration | Meaning |
|----------|---------|
| `PT1M` | 1 minute |
| `PT5M` | 5 minutes |
| `PT15M` | 15 minutes |
| `PT30M` | 30 minutes |
| `PT1H` | 1 hour |
| `PT2H` | 2 hours |
| `PT6H` | 6 hours |
| `PT12H` | 12 hours |
| `P1D` | 1 day |
| `P7D` | 7 days |
| `P30D` | 30 days |
| `P90D` | 90 days |
| `P1Y` | 1 year |

### Format Rules

- **P** prefix required (Period)
- **T** separator for time components
- Supports: Years (Y), Months (M), Weeks (W), Days (D), Hours (H), Minutes (M), Seconds (S)

**Examples**:

```javascript
'P1Y2M3DT4H5M6S'  // 1 year, 2 months, 3 days, 4 hours, 5 minutes, 6 seconds
'P7D'              // 7 days
'PT2H30M'          // 2 hours 30 minutes
'P1W'              // 1 week (7 days)
```

## Complete Examples

### Account Security

```javascript
// Lock account after failed login attempts
state.user.status == 'active' AND
COUNT event.user.failed.login
  WHERE user_id == 'user-123'
  IN 'PT15M' >= 5
```

### High-Value Customer Rewards

```javascript
// Reward customers with 3+ large orders in 30 days
state.user.tier IN ['gold', 'platinum'] AND
state.account.verified AND
COUNT event.order.placed
  WHERE customer_id == 'cust-123' AND amount >= 1000
  IN 'P30D' >= 3
```

### Support Ticket Escalation

```javascript
// Escalate if high-priority ticket not responded to
tag.priority IN ['high', 'critical'] AND
state.ticket.status == 'open' AND
NOT event.agent.responded.ticket IN 'PT2H'
```

### Email Validation

```javascript
// Verify corporate email from allowed domains
state.user.email EXISTS AND
(state.user.email ENDS_WITH '@company.com' OR
 state.user.email ENDS_WITH '@subsidiary.com') AND
state.user.verified
```

### Rate Limiting

```javascript
// Block excessive API calls
COUNT event.user.called.api
  WHERE user_id == 'user-456'
  IN 'PT1M' > 100
```

### Multi-Factor Authentication

```javascript
// Require MFA for sensitive actions from new locations
state.user.location_new AND
event.user.performed.sensitive_action AND
NOT state.user.mfa_verified
```

### Customer Engagement

```javascript
// Identify engaged users for beta features
COUNT event.user.clicked.button IN 'P7D' >= 20 AND
COUNT event.user.viewed.page IN 'P7D' >= 50 AND
state.user.tier == 'premium' AND
state.account.age > 90
```

### Cross-Project Coordination

```javascript
// Multi-service authentication flow
// Ensure user is authenticated in auth service before allowing checkout
event.auth_service.user.logged.in IN 'PT24H' AND
state.user.verified AND
NOT event.payment_service.payment.failed IN 'PT1H'

// Cross-service error correlation
// Detect when API gateway sees errors but services are healthy
COUNT event.api_gateway.request.failed IN 'PT5M' >= 10 AND
NOT event.backend_service.error.occurred IN 'PT5M' AND
NOT event.database_service.connection.failed IN 'PT5M'

// Distributed workflow coordination
// Trigger action only if events occurred in correct order across services
event.order_service.order.created IN 'PT1H' AND
event.payment_service.payment.completed IN 'PT1H' AND
event.inventory_service.items.reserved IN 'PT1H' AND
NOT event.notification_service.email.sent IN 'PT1H'
```