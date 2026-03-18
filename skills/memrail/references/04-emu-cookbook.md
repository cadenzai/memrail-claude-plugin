# EMU Cookbook

**Common Patterns and Real-World Examples**

> **Note**: This cookbook uses the **modern DSL syntax** with dot notation (`state.user.tier == 'premium'`) introduced in AMI v2. See [DSL Reference](02-dsl-reference.md) for complete syntax documentation.

## Table of Contents

- [Customer Support](#customer-support)
- [Sales & Lead Management](#sales--lead-management)
- [Operations & Infrastructure](#operations--infrastructure)
- [Client Success](#client-success)
- [Growth & Marketing](#growth--marketing)
- [Engineering & Incidents](#engineering--incidents)
- [Security](#security)
- [Advanced DSL Features](#advanced-dsl-features)
- [Common Patterns](#common-patterns)

## Customer Support

### 1. VIP Escalation

**Use case**: Automatically escalate high-priority tickets from VIP customers to specialist team.

```json
{
    "emu_key": "support.vip_escalation",
    "trigger": "state.customer.tier == 'vip' AND state.ticket.priority >= 'high' AND NOT event.agent.escalated.ticket IN 'PT2H'",
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_TO_VIP_TEAM",
        "tool": {
            "tool_id": "zendesk_escalator",
            "version": "2.1.0",
            "args": {
                "queue": "vip-support",
                "priority": "critical",
                "notify_manager": true,
                "sla_override": "1h"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 7200, "gate": "activation"},
        "exclusion_groups": ["escalation_actions"]
    },
    "expected_utility": 0.95,
    "confidence": 0.88,
    "intent": "Escalate high-priority VIP tickets to specialist team within 1 hour"
}
```

**ATOM Dependencies**:
- `state.customer.tier` - From CRM system
- `state.ticket.priority` - From ticket system
- `event.agent.escalated.ticket` - Ingested on escalation

**Pattern**: High-value customer + high-priority issue + no recent escalation

### 2. SLA Breach Prevention

**Use case**: Alert when ticket is close to breaching SLA.

```json
{
    "emu_key": "support.sla_breach_prevention",
    "trigger": "state.ticket.sla_remaining_hours <= 2 AND state.ticket.status != 'resolved'",
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_FOR_SLA",
        "tool": {
            "tool_id": "ticket_escalator",
            "version": "1.4.0",
            "args": {
                "escalation_level": "supervisor",
                "reason": "sla_breach_imminent",
                "notify_channels": ["#support-escalations", "#management"],
                "priority": "urgent"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 3600, "gate": "activation"}
    },
    "expected_utility": 0.95,
    "confidence": 0.88
}
```

**Pattern**: Time-based urgency + unresolved status

### 3. Language-Based Routing

**Use case**: Route tickets to language-specific support teams.

```json
{
    "emu_key": "support.language_routing",
    "trigger": "tag.language IN ['spanish', 'french', 'german']",
    "action": {
        "type": "route",
        "destination": "language_specific_queue",
        "metadata": {
            "language": "{{language}}",
            "priority": "standard"
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 8,
        "cooldown": {"seconds": 0, "gate": "activation"}
    },
    "expected_utility": 0.90,
    "confidence": 0.95
}
```

**ATOM Dependencies**:
- `tag.language` - From ML language detector or user profile

**Pattern**: ML classification → Routing (uses `IN` operator for multi-value matching)

### 4. Follow-up Automation

**Use case**: Send automated follow-up when customer hasn't responded in 48 hours.

```json
{
    "emu_key": "support.followup_automation",
    "trigger": "state.ticket.status == 'waiting_customer' AND state.ticket.last_contact_hours >= 48 AND NOT event.system.sent.followup IN 'PT24H'",
    "action": {
        "type": "tool_call",
        "intent": "SEND_FOLLOWUP_EMAIL",
        "tool": {
            "tool_id": "email_service",
            "version": "1.5.0",
            "args": {
                "template_id": "followup_template",
                "to": "{{customer.email}}",
                "ticket_id": "{{ticket.id}}",
                "urgency": "normal"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 5,
        "cooldown": {"seconds": 86400, "gate": "activation"}
    },
    "expected_utility": 0.75,
    "confidence": 0.82
}
```

**Pattern**: Waiting state + time threshold + prevent duplicate sends

### 5. Knowledge Base Suggestion

**Use case**: Suggest KB articles for common issues before escalating.

```json
{
    "emu_key": "support.kb_suggestion",
    "trigger": "tag.category IN ['password_reset', 'account_setup']",
    "action": {
        "type": "context_directive",
        "directive": "Suggest relevant knowledge base articles for {{ticket.category}} before manual intervention. Articles: KB-{{ticket.category}}-001, KB-{{ticket.category}}-002"
    },
    "policy": {
        "mode": "advisory",
        "priority": 3,
        "cooldown": {"seconds": 0, "gate": "activation"}
    },
    "expected_utility": 0.65,
    "confidence": 0.90
}
```

**Pattern**: Category-based guidance

## Sales & Lead Management

### 1. Lead Qualification

**Use case**: Automatically qualify high-value leads.

```json
{
    "emu_key": "sales.lead_qualification",
    "trigger": "state.lead.source == 'website' AND state.lead.company_size >= 100 AND tag.intent == 'demo_request'",
    "action": {
        "type": "tool_call",
        "intent": "CREATE_QUALIFIED_LEAD",
        "tool": {
            "tool_id": "salesforce",
            "version": "3.0.0",
            "args": {
                "lead_score": "hot",
                "assign_to": "enterprise_team",
                "priority": "high",
                "follow_up_hours": 2
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 8,
        "cooldown": {"seconds": 3600, "gate": "activation"}
    },
    "expected_utility": 0.92,
    "confidence": 0.87
}
```

**ATOM Dependencies**:
- `state.lead.source` - From form submission
- `state.lead.company_size` - From enrichment API
- `tag.intent` - From ML intent classifier

**Pattern**: Multiple qualifying criteria → Automated action

### 2. Proposal Generation

**Use case**: Present proposal generation options after discovery call.

```json
{
    "emu_key": "sales.proposal_generation",
    "trigger": "state.lead.status == 'qualified' AND state.lead.budget >= 50000 AND event.sales_rep.completed.discovery_call IN 'PT72H'",
    "action": {
        "type": "decision_prompt",
        "message": "Lead {{lead.company}} ({{lead.budget}} budget) completed discovery. Generate proposal?",
        "options": [
            {"id": "generate_standard", "label": "Generate Standard Proposal"},
            {"id": "generate_custom", "label": "Generate Custom Proposal"},
            {"id": "schedule_followup", "label": "Schedule Follow-up Call"}
        ]
    },
    "policy": {
        "mode": "require_human",
        "priority": 7,
        "cooldown": {"seconds": 0, "gate": "activation"}
    },
    "expected_utility": 0.88,
    "confidence": 0.75
}
```

**Pattern**: Event-triggered human decision

### 3. Deal Closing Alert

**Use case**: Notify team when deal is close to closing.

```json
{
    "emu_key": "sales.deal_alerts",
    "trigger": "state.deal.stage == 'negotiation' AND state.deal.close_date_days <= 7 AND state.deal.probability >= 80",
    "action": {
        "type": "tool_call",
        "intent": "SEND_DEAL_ALERT",
        "tool": {
            "tool_id": "slack_notifier",
            "version": "1.2.0",
            "args": {
                "channel": "#sales-alerts",
                "deal_id": "{{deal.id}}",
                "amount": "{{deal.value}}",
                "close_date": "{{deal.close_date}}"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 6,
        "cooldown": {"seconds": 86400, "gate": "activation"}
    },
    "expected_utility": 0.80,
    "confidence": 0.90
}
```

**Pattern**: Pipeline stage + timing + probability threshold

### 4. Price Negotiation Guidance

**Use case**: Provide guidance when large discount requested.

```json
{
    "emu_key": "sales.price_negotiation",
    "trigger": "state.deal.discount_requested > 15 AND state.deal.value >= 100000",
    "action": {
        "type": "context_directive",
        "directive": "For deals over $100k requesting >15% discount, require VP approval and consider value-add alternatives (extended support, training, etc.) instead of pure discount"
    },
    "policy": {
        "mode": "advisory",
        "priority": 5,
        "cooldown": {"seconds": 0, "gate": "activation"}
    },
    "expected_utility": 0.85,
    "confidence": 0.80
}
```

**Pattern**: Business rule enforcement via guidance

## Operations & Infrastructure

### 1. System Health Alert

**Use case**: Alert on-call when system resources are critical.

```json
{
    "emu_key": "ops.system_health_alert",
    "trigger": "state.system.cpu_usage >= 85 AND state.system.memory_usage >= 90 AND NOT event.system.sent.health_alert IN 'PT30M'",
    "action": {
        "type": "tool_call",
        "intent": "SEND_SYSTEM_ALERT",
        "tool": {
            "tool_id": "pagerduty",
            "version": "2.0.0",
            "args": {
                "severity": "high",
                "service": "{{system.name}}",
                "description": "High resource usage detected: CPU {{system.cpu_usage}}%, Memory {{system.memory_usage}}%",
                "escalation_policy": "ops_team"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 1800, "gate": "activation"}
    },
    "expected_utility": 0.95,
    "confidence": 0.92
}
```

**Pattern**: Multiple resource thresholds + cooldown to prevent alert fatigue

### 2. Compliance Check

**Use case**: Trigger compliance review on sensitive data access.

```json
{
    "emu_key": "ops.compliance_check",
    "trigger": "state.audit.last_check_days >= 30 OR event.user.accessed.sensitive_data IN 'PT1H'",
    "action": {
        "type": "decision_prompt",
        "message": "Compliance check triggered. Review access logs and audit trail?",
        "options": [
            {"id": "run_audit", "label": "Run Full Audit"},
            {"id": "quick_check", "label": "Quick Compliance Check"},
            {"id": "schedule_later", "label": "Schedule for Later"}
        ]
    },
    "policy": {
        "mode": "advisory",
        "priority": 7,
        "cooldown": {"seconds": 3600, "gate": "activation"}
    },
    "expected_utility": 0.82,
    "confidence": 0.78
}
```

**Pattern**: Scheduled check OR event-triggered review

### 3. Workflow Automation

**Use case**: Auto-provision access when approval granted.

```json
{
    "emu_key": "ops.workflow_automation",
    "trigger": "state.request.type == 'access_provision' AND state.request.approval_status == 'approved' AND tag.department == 'engineering'",
    "action": {
        "type": "tool_call",
        "intent": "EXECUTE_WORKFLOW",
        "tool": {
            "tool_id": "workflow_engine",
            "version": "1.8.0",
            "args": {
                "workflow_id": "engineering_access_provision",
                "request_id": "{{request.id}}",
                "user_id": "{{request.user_id}}",
                "permissions": "{{request.permissions}}"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 6,
        "cooldown": {"seconds": 0, "gate": "activation"}
    },
    "expected_utility": 0.88,
    "confidence": 0.95
}
```

**Pattern**: Approval workflow + department context

## Client Success

### 1. Account Health Monitoring

**Use case**: Alert CSM when high-value account health declines.

```json
{
    "emu_key": "client_success.account_health",
    "trigger": "state.account.health_score <= 60 AND state.account.contract_value >= 500000 AND NOT event.csm.contacted.client IN 'P7D'",
    "action": {
        "type": "decision_prompt",
        "message": "Account {{account.name}} (${{account.contract_value}}) has declining health score ({{account.health_score}}). Action needed?",
        "options": [
            {"id": "schedule_call", "label": "Schedule Health Check Call"},
            {"id": "send_survey", "label": "Send Health Survey"},
            {"id": "escalate_csm", "label": "Escalate to Senior CSM"},
            {"id": "monitor_more", "label": "Monitor for Another Week"}
        ]
    },
    "policy": {
        "mode": "require_human",
        "priority": 8,
        "cooldown": {"seconds": 604800, "gate": "activation"}
    },
    "expected_utility": 0.88,
    "confidence": 0.82
}
```

**Pattern**: Health score threshold + contract value + no recent contact

### 2. Contract Renewal Preparation

**Use case**: Automatically initiate renewal process 90 days before expiry.

```json
{
    "emu_key": "client_success.renewal_automation",
    "trigger": "state.contract.days_to_expiry <= 90 AND state.account.renewal_probability >= 80",
    "action": {
        "type": "tool_call",
        "intent": "INITIATE_RENEWAL_PROCESS",
        "tool": {
            "tool_id": "contract_manager",
            "version": "2.2.0",
            "args": {
                "contract_id": "{{contract.id}}",
                "current_value": "{{contract.value}}",
                "renewal_probability": "{{account.renewal_probability}}",
                "csm_assigned": "{{account.csm_email}}",
                "priority": "high"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 7,
        "cooldown": {"seconds": 86400, "gate": "activation"}
    },
    "expected_utility": 0.92,
    "confidence": 0.88
}
```

**Pattern**: Time-to-expiry + renewal likelihood

## Growth & Marketing

### 1. Onboarding Optimization

**Use case**: Send nudge email to users stuck in onboarding.

```json
{
    "emu_key": "growth.onboarding_optimization",
    "trigger": "state.user.signup_completed AND state.user.onboarding_step <= 2 AND state.user.signup_hours_ago >= 24",
    "action": {
        "type": "tool_call",
        "intent": "SEND_ONBOARDING_NUDGE",
        "tool": {
            "tool_id": "email_automation",
            "version": "2.0.0",
            "args": {
                "template": "onboarding_nudge",
                "user_email": "{{user.email}}",
                "current_step": "{{user.onboarding_step}}",
                "product_tips": true
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 8,
        "cooldown": {"seconds": 43200, "gate": "activation"}
    },
    "expected_utility": 0.78,
    "confidence": 0.85
}
```

**Pattern**: Signup + stalled progress + time threshold

### 2. Retention Campaign

**Use case**: Win-back campaign for inactive paid users.

```json
{
    "emu_key": "growth.retention_campaign",
    "trigger": "state.user.last_login_days >= 14 AND state.user.tier == 'paid' AND NOT event.marketing.sent.retention_email IN 'P30D'",
    "action": {
        "type": "tool_call",
        "intent": "SEND_RETENTION_EMAIL",
        "tool": {
            "tool_id": "marketing_automation",
            "version": "1.3.0",
            "args": {
                "campaign": "win_back",
                "user_segment": "{{user.tier}}",
                "personalization": true,
                "discount_offer": "20_percent"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 5,
        "cooldown": {"seconds": 2592000, "gate": "activation"}
    },
    "expected_utility": 0.70,
    "confidence": 0.80
}
```

**Pattern**: Inactivity + paid tier + no recent campaign

## Engineering & Incidents

### 1. Incident Response

**Use case**: Auto-trigger incident response when error rate spikes.

```json
{
    "emu_key": "engineering.incident_response",
    "trigger": "state.system.error_rate >= 5 AND state.system.response_time_ms >= 2000 AND NOT event.system.triggered.incident_response IN 'PT10M'",
    "action": {
        "type": "tool_call",
        "intent": "TRIGGER_INCIDENT_RESPONSE",
        "tool": {
            "tool_id": "incident_manager",
            "version": "1.5.0",
            "args": {
                "severity": "medium",
                "affected_service": "{{system.name}}",
                "error_rate": "{{system.error_rate}}",
                "response_time": "{{system.response_time_ms}}",
                "notify_oncall": true
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 600, "gate": "activation"}
    },
    "expected_utility": 0.93,
    "confidence": 0.90
}
```

**Pattern**: Multiple error signals + cooldown for incident management

## Security

### 1. Threat Detection

**Use case**: Block IP after multiple failed login attempts.

```json
{
    "emu_key": "security.threat_detection",
    "trigger": "COUNT event.user.failed.login IN 'PT10M' >= 5 AND tag.source == 'external'",
    "action": {
        "type": "tool_call",
        "intent": "BLOCK_SUSPICIOUS_IP",
        "tool": {
            "tool_id": "security_manager",
            "version": "3.1.0",
            "args": {
                "action": "temporary_block",
                "ip_address": "{{ip_address}}",
                "duration_minutes": 60,
                "reason": "multiple_failed_logins",
                "notify_security_team": true
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 1800, "gate": "activation"}
    },
    "expected_utility": 0.95,
    "confidence": 0.92
}
```

**Pattern**: Threshold-based security response with ergonomic event counting

## Advanced DSL Features

### 1. String Operations (STARTS_WITH, ENDS_WITH, CONTAINS, MATCHES)

**Use case**: Email domain validation and content filtering.

```json
{
    "emu_key": "security.corporate_email_validation",
    "trigger": "state.user.email EXISTS AND (state.user.email ENDS_WITH '@company.com' OR state.user.email ENDS_WITH '@subsidiary.com') AND NOT state.user.verified",
    "action": {
        "type": "tool_call",
        "intent": "SEND_VERIFICATION_EMAIL",
        "tool": {
            "tool_id": "email_verifier",
            "version": "1.0.0",
            "args": {
                "template": "corporate_verification",
                "priority": "high"
            }
        }
    },
    "policy": {"mode": "auto", "priority": 7}
}
```

**DSL Features Demonstrated**:
- `EXISTS` operator - Check field presence before using it
- `ENDS_WITH` - String suffix matching for email domains
- Logical `OR` - Multiple domain support

**Other String Operations**:
```javascript
// Prefix matching
state.user.role STARTS_WITH 'admin-'

// Substring search
state.message CONTAINS 'urgent' OR state.message CONTAINS 'CRITICAL'

// Regex pattern matching
state.code MATCHES '^[A-Z]{3}-\d{4}$'
state.phone MATCHES '^\+1-\d{3}-\d{3}-\d{4}$'
```

### 2. WHERE Clause Filtering (Attribute-Level Event Filtering)

**Use case**: Security monitoring for specific user actions.

```json
{
    "emu_key": "security.user_session_monitoring",
    "trigger": "COUNT event.user.failed.login WHERE user_id == 'user-123' IN 'PT15M' >= 3 AND NOT event.security.notified.user WHERE user_id == 'user-123' IN 'PT1H'",
    "action": {
        "type": "tool_call",
        "intent": "SEND_SECURITY_ALERT",
        "tool": {
            "tool_id": "security_notifier",
            "version": "2.0.0",
            "args": {
                "alert_type": "failed_login_threshold",
                "user_id": "{{user_id}}",
                "threshold": 3
            }
        }
    },
    "policy": {"mode": "auto", "priority": 9}
}
```

**DSL Features Demonstrated**:
- `COUNT ... WHERE` - Event counting with attribute filtering
- Multiple `WHERE` clauses - Filter both counting and existence checks
- Attribute equality - `user_id == 'user-123'`

**WHERE Clause Use Cases**:
```javascript
// Order tracking - Did THIS order ship?
event.order.shipped WHERE order_id == 'ord-456' IN 'P7D'

// Multi-attribute filtering
COUNT event.purchase.completed WHERE customer_id == 'cust-123' AND amount >= 1000 IN 'P30D' >= 3

// Session activity
COUNT event.user.clicked.button WHERE session_id == 'sess-789' IN 'PT1H' > 10
```

### 3. IN Operator (List Membership)

**Use case**: Multi-tier customer routing.

```json
{
    "emu_key": "support.premium_routing",
    "trigger": "state.user.tier IN ['gold', 'platinum', 'diamond'] AND state.ticket.status == 'new'",
    "action": {
        "type": "route",
        "destination": "premium_support_queue",
        "metadata": {
            "tier": "{{user.tier}}",
            "priority": "high",
            "sla": "2h"
        }
    },
    "policy": {"mode": "auto", "priority": 9}
}
```

**DSL Features Demonstrated**:
- `IN` operator - Check membership in list of values
- Case-insensitive matching - 'Gold', 'GOLD', 'gold' all match

**IN Operator Use Cases**:
```javascript
// Multiple status checks
state.ticket.status IN ['open', 'pending', 'waiting_customer']

// Role-based access
state.user.role IN ['admin', 'moderator', 'owner']

// Country/region filtering
state.user.country IN ['US', 'CA', 'MX']

// Tag classification
tag.priority IN ['high', 'critical']
tag.category IN ['billing', 'support', 'sales']
```

### 4. Cross-Project Event Queries

**Use case**: Multi-service authentication workflow.

```json
{
    "emu_key": "workflow.authenticated_checkout",
    "trigger": "event.auth_service.user.logged.in IN 'PT24H' AND state.cart.total >= 100 AND NOT event.payment_service.payment.failed IN 'PT1H'",
    "action": {
        "type": "tool_call",
        "intent": "ENABLE_CHECKOUT",
        "tool": {
            "tool_id": "checkout_enabler",
            "version": "1.0.0",
            "args": {
                "cart_id": "{{cart.id}}",
                "user_authenticated": true
            }
        }
    },
    "policy": {"mode": "auto", "priority": 8}
}
```

**DSL Features Demonstrated**:
- Cross-project events - `event.PROJECT_NAME.subject.verb.object`
- Multi-service coordination - Auth + Payment services

**Cross-Project Use Cases**:
```javascript
// Multi-service error correlation
COUNT event.api_gateway.request.failed IN 'PT5M' >= 10 AND
NOT event.backend_service.error.occurred IN 'PT5M'

// Distributed workflow tracking
event.order_service.order.created IN 'PT1H' AND
event.payment_service.payment.completed IN 'PT1H' AND
event.inventory_service.items.reserved IN 'PT1H' AND
NOT event.notification_service.email.sent IN 'PT1H'

// Authentication flow
event.auth_service.user.logged.in IN 'PT24H' AND
event.shop_service.user.initiated.checkout
```

### 5. Boolean Shorthand

**Use case**: Feature flag and permission checks.

```json
{
    "emu_key": "feature.beta_access",
    "trigger": "state.user.verified AND state.user.premium AND state.feature.beta_enabled AND NOT state.user.banned",
    "action": {
        "type": "context_directive",
        "directive": "User has access to beta features. Enable advanced UI components and experimental tools."
    },
    "policy": {"mode": "advisory", "priority": 5}
}
```

**DSL Features Demonstrated**:
- Boolean shorthand - `state.field` instead of `state.field == true`
- Multiple boolean checks with AND/NOT

**Boolean Shorthand Use Cases**:
```javascript
// Account flags
state.user.verified AND state.account.active AND NOT state.user.suspended

// Feature flags
state.feature.new_ui_enabled AND state.user.beta_tester

// Permission checks
state.user.admin OR state.user.moderator
```

### 6. Complex Composition

**Use case**: High-value churn risk detection.

```json
{
    "emu_key": "retention.churn_risk_vip",
    "trigger": "(state.user.tier IN ['gold', 'platinum', 'diamond']) AND (state.account.health_score <= 60) AND (COUNT event.user.logged.in IN 'P30D' < 3) AND (state.account.contract_value >= 100000) AND NOT event.csm.contacted.client IN 'P7D'",
    "action": {
        "type": "decision_prompt",
        "message": "HIGH PRIORITY: VIP account {{account.name}} (${{account.contract_value}}) showing churn signals. Health: {{account.health_score}}, Logins (30d): <3. Action required?",
        "options": [
            {"id": "executive_call", "label": "Schedule Executive Check-in Call"},
            {"id": "account_review", "label": "Trigger Account Health Review"},
            {"id": "custom_offer", "label": "Prepare Retention Offer"},
            {"id": "monitor", "label": "Monitor for Another Week"}
        ]
    },
    "policy": {
        "mode": "require_human",
        "priority": 10,
        "cooldown": {"seconds": 604800, "gate": "activation"}
    },
    "expected_utility": 0.92,
    "confidence": 0.85
}
```

**DSL Features Demonstrated**:
- Parentheses grouping - Clear logical structure
- Mixed operators - `IN`, `<=`, `<`, `>=`, `NOT`
- Event counting - `COUNT event.user.logged.in IN 'P30D' < 3`
- Complex multi-condition logic

## Common Patterns

### Pattern 1: Time-Based Triggers

**Use case**: Trigger action after specific time period.

```javascript
// Pattern
state.entity.hours_since_last_action >= THRESHOLD

// Examples
state.ticket.hours_since_response >= 24
state.user.days_since_login >= 7
state.contract.days_to_expiry <= 90
```

### Pattern 2: Prevent Duplicate Actions

**Use case**: Ensure action only fires once per time window.

```javascript
// Pattern
CONDITION AND NOT event.action.performed.target IN 'DURATION'

// Examples
state.user.tier == 'vip' AND NOT event.agent.sent.welcome_email IN 'P7D'
state.alert.severity == 'critical' AND NOT event.system.sent.alert IN 'PT30M'
```

### Pattern 3: Multi-Threshold Alerts

**Use case**: Trigger when multiple metrics exceed thresholds.

```javascript
// Pattern
state.metric1 >= THRESHOLD1 AND state.metric2 >= THRESHOLD2

// Examples
state.system.cpu_usage >= 85 AND state.system.memory_usage >= 90
state.deal.size >= 100000 AND state.deal.discount_requested > 15
```

### Pattern 4: Conditional Routing

**Use case**: Route based on classification/metadata.

```javascript
// Pattern (using IN operator - modern approach)
tag.CATEGORY IN ['VALUE1', 'VALUE2', ...]

// Pattern (using OR - explicit approach)
tag.CATEGORY == 'VALUE1' OR tag.CATEGORY == 'VALUE2'

// Examples
tag.language IN ['spanish', 'french', 'german']
tag.priority == 'high' AND tag.department == 'engineering'
```

### Pattern 5: Event Rate Limiting

**Use case**: Trigger when event frequency exceeds threshold.

```javascript
// Pattern (ergonomic syntax - recommended)
COUNT event.TOPIC IN 'DURATION' >= THRESHOLD

// Examples
COUNT event.user.login.failed IN 'PT10M' >= 5
COUNT event.api.called.endpoint IN 'PT1H' > 100

// With attribute filtering
COUNT event.user.clicked.button WHERE user_id == 'user-123' IN 'PT1H' > 10
```

### Pattern 6: Exclusivity (Either/Or)

**Use case**: Fire only one EMU from a group.

```json
// Pattern: Use exclusion_groups
{
    "policy": {
        "exclusion_groups": ["group_name"]
    }
}

// Example: Only one escalation EMU fires
[
  {
    "emu_key": "escalate_vip",
    "trigger": "state.customer.tier == 'vip' AND state.ticket.priority >= 'high'",
    "policy": {"exclusion_groups": ["escalations"], "priority": 9},
    "action": {"type": "route", "destination": "vip_queue"}
  },
  {
    "emu_key": "escalate_high_priority",
    "trigger": "state.ticket.priority >= 'high'",
    "policy": {"exclusion_groups": ["escalations"], "priority": 7},
    "action": {"type": "route", "destination": "priority_queue"}
  }
]
// Only highest priority (vip) fires if both match
```

### Pattern 7: Staged Rollout

**Use case**: Test EMU before full rollout.

```python
# Stage 1: Shadow mode (evaluate but don't execute)
{
    "state": "shadow"
}

# Stage 2: Canary mode (10% traffic)
{
    "state": "canary"
}

# Stage 3: Full rollout
{
    "state": "active"
}
```

### Pattern 8: Business Hours vs After Hours

**Use case**: Different behavior based on time.

```json
// Business hours
{
    "emu_key": "support.business_hours_routing",
    "trigger": "tag.time_of_day == 'business_hours'",
    "policy": {"priority": 5},
    "action": {"type": "route", "destination": "standard_queue"}
}

// After hours (higher priority)
{
    "emu_key": "support.after_hours_escalation",
    "trigger": "tag.time_of_day == 'after_hours' AND state.ticket.priority == 'high'",
    "policy": {"priority": 9},
    "action": {"type": "tool_call", "intent": "PAGE_ONCALL"}
}
```

### Pattern 9: ML-Augmented Decisions

**Use case**: Use ML classification to inform action.

```json
{
    "emu_key": "retention.churn_prevention",
    "trigger": "tag.sentiment == 'negative' AND tag.intent == 'cancel' AND state.customer.lifetime_value > 5000",
    "action": {
        "type": "decision_prompt",
        "message": "High-value customer (${{customer.lifetime_value}}) expressing cancellation intent with negative sentiment. Escalate?",
        "options": [
            {"id": "escalate_csm", "label": "Escalate to Senior CSM"},
            {"id": "offer_incentive", "label": "Prepare Retention Offer"}
        ]
    },
    "policy": {"mode": "require_human", "priority": 9}
}
```

**ATOM Dependencies**:
- `tag.sentiment` - From sentiment classifier
- `tag.intent` - From intent classifier
- `state.customer.lifetime_value` - From analytics

### Pattern 10: Cross-Project Correlation

**Use case**: React to events from another project.

```json
{
    "emu_key": "workflow.cross_project_coordination",
    "trigger": "event.project_b.agent.escalated.case IN 'PT2H' AND state.team.capacity < 80",
    "action": {
        "type": "context_directive",
        "directive": "Case escalated from Project B. Current team capacity: {{team.capacity}}%. Consider load balancing or requesting additional resources."
    },
    "policy": {"mode": "advisory", "priority": 6}
}
```

**Cross-Project Event Syntax**:
```javascript
// 4-part notation: event.PROJECT_NAME.subject.verb.object
event.auth_service.user.logged.in IN 'PT24H'
event.payment_service.payment.completed IN 'PT1H'
COUNT event.analytics_proj.user.viewed.page IN 'P7D' >= 50
```

## Complete Example: Support Automation Suite

Here's a complete suite of EMUs for support automation using modern DSL syntax:

```json
// 1. VIP Fast-Track (Highest Priority)
{
    "emu_key": "support.vip_fast_track",
    "trigger": "state.customer.tier == 'vip' AND state.ticket.priority >= 'high'",
    "policy": {"priority": 10, "mode": "auto", "exclusion_groups": ["routing"]},
    "action": {"type": "route", "destination": "vip_queue"}
}

// 2. SLA Watch (Critical Threshold)
{
    "emu_key": "support.sla_watch",
    "trigger": "state.ticket.sla_remaining_hours <= 2 AND state.ticket.status != 'resolved'",
    "policy": {"priority": 9, "mode": "auto", "exclusion_groups": ["escalation"]},
    "action": {"type": "tool_call", "intent": "ESCALATE_FOR_SLA", "tool": {"tool_id": "escalator"}}
}

// 3. Language Routing (Modern IN operator)
{
    "emu_key": "support.language_route",
    "trigger": "tag.language IN ['spanish', 'french', 'german']",
    "policy": {"priority": 8, "mode": "auto", "exclusion_groups": ["routing"]},
    "action": {"type": "route", "destination": "{{language}}_queue"}
}

// 4. After-Hours High Priority
{
    "emu_key": "support.after_hours_urgent",
    "trigger": "tag.time_of_day == 'after_hours' AND state.ticket.priority == 'urgent'",
    "policy": {"priority": 9, "mode": "auto"},
    "action": {"type": "tool_call", "intent": "PAGE_ONCALL", "tool": {"tool_id": "pagerduty"}}
}

// 5. Follow-Up Reminder (Time-based + event prevention)
{
    "emu_key": "support.followup_reminder",
    "trigger": "state.ticket.status == 'waiting' AND state.ticket.hours_since_update >= 48 AND NOT event.system.sent.followup IN 'PT24H'",
    "policy": {"priority": 5, "mode": "auto"},
    "action": {"type": "tool_call", "intent": "SEND_FOLLOWUP", "tool": {"tool_id": "email_service"}}
}

// 6. KB Suggestion (Advisory mode)
{
    "emu_key": "support.kb_suggest",
    "trigger": "tag.category IN ['password_reset', 'account_setup']",
    "policy": {"priority": 3, "mode": "advisory"},
    "action": {"type": "context_directive", "directive": "Suggest KB article {{category}}"}
}

// 7. Satisfaction Survey (Post-resolution)
{
    "emu_key": "support.csat_survey",
    "trigger": "state.ticket.status == 'resolved' AND NOT event.system.sent.survey IN 'P7D'",
    "policy": {"priority": 2, "mode": "auto"},
    "action": {"type": "tool_call", "intent": "SEND_SURVEY", "tool": {"tool_id": "survey_sender"}}
}
```

**Key Features of This Suite**:
- **Modern DSL Syntax**: Uses dot notation (`state.field`, `tag.kind`, `event.topic IN 'duration'`)
- **Priority Ordering**: VIP/SLA (9-10) > Routing (8) > Follow-ups (5) > Suggestions (3) > Surveys (2)
- **Exclusivity Groups**: `routing` ensures only one routing EMU fires
- **Boolean Shorthand**: Implicit `!= 'resolved'` checks
- **Event Prevention**: `NOT event.X IN 'duration'` prevents duplicate actions
- **IN Operator**: Clean multi-value matching for languages and categories
