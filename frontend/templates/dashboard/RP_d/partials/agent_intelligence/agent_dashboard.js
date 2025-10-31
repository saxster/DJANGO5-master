/**
 * Agent Intelligence Dashboard JavaScript
 *
 * Fetches and displays AI agent recommendations in the dashboard.
 * Integrates with Gemini-powered agent API.
 *
 * Phase 5.3: JavaScript Integration
 */

// Global variables for agent intelligence
let agentInsightsCache = null;
let agentStatusCache = null;

/**
 * Load agent insights and inject into dashboard
 */
function loadAgentInsights() {
    $.ajax({
        url: '/api/dashboard/agent-insights/',
        method: 'GET',
        data: {
            from: _from_pd,
            upto: _to_pd
        },
        success: function(data) {
            if (data.status === 'success') {
                agentInsightsCache = data.agent_insights;

                // Update LLM provider badge
                $('#llm-provider-badge').text(data.summary.llm_provider || 'Gemini');

                // Inject recommendations into each module
                Object.keys(data.agent_insights).forEach(module => {
                    const recommendations = data.agent_insights[module];
                    injectRecommendations(module, recommendations);
                });

                // Show summary notification if high-priority recommendations exist
                showAgentSummaryNotification(data.summary);
            }
        },
        error: function(xhr, status, error) {
            console.error('Failed to load agent insights:', error);
        }
    });
}

/**
 * Load agent status and activity feed
 */
function loadAgentStatus() {
    $.ajax({
        url: '/api/dashboard/agent-status/',
        method: 'GET',
        success: function(data) {
            if (data.status === 'success') {
                agentStatusCache = data;
                updateAgentStatusTable(data.agent_status);
                updateActivityFeed(data.activity_feed);
            }
        },
        error: function(xhr, status, error) {
            console.error('Failed to load agent status:', error);
            // Show error message in table
            $('#agent-status-tbody').html(
                '<tr><td colspan="4" class="text-center text-danger">Failed to load agent status</td></tr>'
            );
        }
    });
}

/**
 * Update agent status table
 */
function updateAgentStatusTable(agentStatus) {
    const tbody = $('#agent-status-tbody');
    tbody.empty();

    if (!agentStatus || agentStatus.length === 0) {
        tbody.html('<tr><td colspan="4" class="text-center text-muted">No agent activity</td></tr>');
        return;
    }

    agentStatus.forEach(agent => {
        const statusBadge = agent.status === 'active'
            ? '<span class="badge badge-sm badge-success">Active</span>'
            : '<span class="badge badge-sm badge-secondary">Idle</span>';

        tbody.append(`
            <tr>
                <td class="fw-semibold">${agent.agent}</td>
                <td class="text-muted">${agent.last_action}</td>
                <td>${statusBadge}</td>
                <td class="text-end">${agent.confidence}</td>
            </tr>
        `);
    });
}

/**
 * Update agent activity feed timeline
 */
function updateActivityFeed(activityFeed) {
    const feed = $('#agent-activity-feed');
    feed.empty();

    if (!activityFeed || activityFeed.length === 0) {
        feed.html('<div class="text-center text-muted py-3">No recent activity</div>');
        return;
    }

    activityFeed.forEach(activity => {
        const severityIcon = getSeverityIcon(activity.severity);

        feed.append(`
            <div class="timeline-item pb-3">
                <span class="fw-bold text-gray-800">${activity.timestamp}</span> –
                ${severityIcon}
                <span class="fw-semibold">${activity.agent}</span>
                <span class="text-gray-700">${activity.action}</span>
            </div>
        `);
    });
}

/**
 * Inject recommendations into dashboard module
 */
function injectRecommendations(module, recommendations) {
    const container = $(`.agent-recommendations-container[data-module="${module}"]`);

    if (!container.length) {
        console.warn(`No container found for module: ${module}`);
        return;
    }

    container.empty();

    if (!recommendations || recommendations.length === 0) {
        return; // No recommendations to show
    }

    // Create recommendation cards
    recommendations.forEach(rec => {
        const card = createRecommendationCard(rec);
        container.append(card);
    });
}

/**
 * Create recommendation card from template
 */
function createRecommendationCard(recommendation) {
    const template = document.getElementById('recommendation-card-template');
    const card = template.content.cloneNode(true);
    const cardEl = $(card).find('.agent-recommendation-card');

    // Set data
    cardEl.attr('data-recommendation-id', recommendation.id);
    cardEl.find('.recommendation-summary').text(recommendation.summary);
    cardEl.find('.recommendation-details').text(
        recommendation.details.length > 0
            ? recommendation.details[0].reason
            : ''
    );
    cardEl.find('.badge-severity')
        .addClass(`badge-${recommendation.severity}`)
        .text(recommendation.severity.toUpperCase());
    cardEl.find('.confidence-score').text(Math.round(recommendation.confidence * 100));
    cardEl.find('.agent-name').text(recommendation.agent_name);
    cardEl.find('.llm-provider').text(recommendation.llm_provider || 'Gemini');

    // Create action buttons
    const actionsContainer = cardEl.find('.recommendation-actions');
    actionsContainer.empty();

    recommendation.actions.forEach(action => {
        const button = createActionButton(action, recommendation.id);
        actionsContainer.append(button);
    });

    return cardEl;
}

/**
 * Create action button
 */
function createActionButton(action, recommendationId) {
    const btnClass = action.type === 'workflow_trigger'
        ? 'btn-primary'
        : action.type === 'link'
            ? 'btn-secondary'
            : 'btn-light';

    const button = $(`<button class="btn btn-sm ${btnClass}">${action.label}</button>`);

    // Attach click handler
    button.on('click', function() {
        executeAgentAction(recommendationId, action);
    });

    return button;
}

/**
 * Execute agent action
 */
function executeAgentAction(recommendationId, action) {
    if (action.type === 'link') {
        // Navigate to URL
        window.open(action.url, '_blank');
        return;
    }

    if (action.type === 'workflow_trigger') {
        // Execute via API
        $.ajax({
            url: '/api/dashboard/agent-insights/',
            method: 'POST',
            data: {
                recommendation_id: recommendationId,
                action: action.endpoint,
                csrfmiddlewaretoken: $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(result) {
                show_success_alert('Action executed successfully', 'Success');
                // Refresh agent insights
                loadAgentInsights();
                loadAgentStatus();
            },
            error: function(xhr, status, error) {
                show_error_alert('Failed to execute action: ' + error, 'Error');
            }
        });
    }
}

/**
 * Show summary notification for high-priority recommendations
 */
function showAgentSummaryNotification(summary) {
    const criticalCount = summary.by_severity?.critical || 0;
    const highCount = summary.by_severity?.high || 0;

    if (criticalCount > 0 || highCount > 0) {
        const message = `${criticalCount + highCount} high-priority agent recommendations require attention`;
        // Use existing notification system
        // show_info_alert(message, 'Agent Insights');
    }
}

/**
 * Get severity icon for activity feed
 */
function getSeverityIcon(severity) {
    const icons = {
        'critical': '<i class="bi bi-exclamation-triangle-fill text-danger"></i>',
        'high': '<i class="bi bi-exclamation-circle-fill text-warning"></i>',
        'medium': '<i class="bi bi-info-circle-fill text-info"></i>',
        'low': '<i class="bi bi-check-circle-fill text-success"></i>'
    };
    return icons[severity] || icons['medium'];
}

/**
 * Initialize agent intelligence on page load
 */
$(document).ready(function() {
    // Load agent insights and status
    loadAgentInsights();
    loadAgentStatus();

    // Refresh button handler
    $('#refresh-agents').on('click', function() {
        $(this).find('i').addClass('fa-spin');
        loadAgentInsights();
        loadAgentStatus();
        setTimeout(() => {
            $(this).find('i').removeClass('fa-spin');
        }, 1000);
    });

    // Auto-refresh every 5 minutes
    setInterval(function() {
        loadAgentInsights();
        loadAgentStatus();
    }, 5 * 60 * 1000);
});
