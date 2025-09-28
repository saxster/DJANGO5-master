# DJANGO5 Frontend Integration Contract

This document captures a machine-checkable contract for the Kotlin frontend to interoperate with the Django5 backend. It mirrors the current models, serializers, views, routes, and WebSocket flows present in this repository.

Usage:
- Treat the YAML below as the source of truth for request/response schemas, enums, and WS message formats.
- Use it to validate Kotlin DTOs, Retrofit/Ktor clients, and WS payloads.

```yaml
contract:
  name: DJANGO5-Frontend-Integration
  version: 1.0.0
  generated_at: 2025-09-26T00:00:00Z
  base_urls:
    rest_v1: /api/v1/
    journal_api: /api/v1/journal/api
    wellness_api: /api/v1/wellness/api
    onboarding_api: /api/v1/onboarding
    graphql: /api/graphql
    websocket_sync: /ws/mobile/sync/
  auth:
    rest:
      type: session_cookie
      cookies:
        - sessionid
        - csrftoken
      csrf_header: X-CSRFToken
      cors:
        allow_credentials: true
    websocket:
      channel_stack: channels.auth.AuthMiddlewareStack
      handshake_auth: session_cookie
      url_params:
        - name: device_id
          type: string
          required: true
  enums:
    JournalPrivacyScope:
      - private
      - manager
      - team
      - aggregate
      - shared
    JournalEntryType:
      - site_inspection
      - equipment_maintenance
      - safety_audit
      - training_completed
      - project_milestone
      - team_collaboration
      - client_interaction
      - process_improvement
      - documentation_update
      - field_observation
      - quality_note
      - investigation_note
      - safety_concern
      - personal_reflection
      - mood_check_in
      - gratitude
      - three_good_things
      - daily_affirmations
      - stress_log
      - strength_spotting
      - reframe_challenge
      - daily_intention
      - end_of_shift_reflection
      - best_self_weekly
    WellnessContentCategory:
      - mental_health
      - physical_wellness
      - workplace_health
      - substance_awareness
      - preventive_care
      - sleep_hygiene
      - nutrition_basics
      - stress_management
      - physical_activity
      - mindfulness
    WellnessDeliveryContext:
      - daily_tip
      - pattern_triggered
      - stress_response
      - mood_support
      - energy_boost
      - shift_transition
      - streak_milestone
      - seasonal
      - workplace_specific
      - gratitude_enhancement
    WellnessContentLevel:
      - quick_tip
      - short_read
      - deep_dive
      - interactive
      - video_content
    EvidenceLevel:
      - who_cdc
      - peer_reviewed
      - professional
      - established
      - educational
    WellnessInteractionType:
      - viewed
      - completed
      - bookmarked
      - shared
      - dismissed
      - rated
      - acted_upon
      - requested_more
  components:
    schemas:
      JournalEntryCreate:
        type: object
        required:
          - entry_type
        properties:
          title: { type: string, maxLength: 200 }
          subtitle: { type: string, maxLength: 200 }
          content: { type: string }
          entry_type: { type: string, enum: { $ref: '#/contract/enums/JournalEntryType' } }
          timestamp: { type: string, format: date-time }
          duration_minutes: { type: integer, minimum: 0 }
          privacy_scope: { type: string, enum: { $ref: '#/contract/enums/JournalPrivacyScope' } }
          consent_given: { type: boolean }
          mood_rating: { type: integer, minimum: 1, maximum: 10 }
          mood_description: { type: string, maxLength: 100 }
          stress_level: { type: integer, minimum: 1, maximum: 5 }
          energy_level: { type: integer, minimum: 1, maximum: 10 }
          stress_triggers: { type: array, items: { type: string } }
          coping_strategies: { type: array, items: { type: string } }
          gratitude_items: { type: array, items: { type: string } }
          daily_goals: { type: array, items: { type: string } }
          affirmations: { type: array, items: { type: string } }
          achievements: { type: array, items: { type: string } }
          learnings: { type: array, items: { type: string } }
          challenges: { type: array, items: { type: string } }
          location_site_name: { type: string, maxLength: 200 }
          location_address: { type: string }
          location_coordinates:
            type: object
            nullable: true
            properties:
              lat: { type: number, minimum: -90, maximum: 90 }
              lng: { type: number, minimum: -180, maximum: 180 }
            required: [lat, lng]
          location_area_type: { type: string, maxLength: 100 }
          team_members: { type: array, items: { type: string } }
          tags: { type: array, items: { type: string } }
          priority: { type: string, maxLength: 20 }
          severity: { type: string, maxLength: 20 }
          completion_rate: { type: number, minimum: 0.0, maximum: 1.0 }
          efficiency_score: { type: number, minimum: 0.0, maximum: 10.0 }
          quality_score: { type: number, minimum: 0.0, maximum: 10.0 }
          items_processed: { type: integer, minimum: 0 }
          is_bookmarked: { type: boolean }
          is_draft: { type: boolean }
          mobile_id: { type: string }
          metadata: { type: object, additionalProperties: true }
        x-rules:
          - if entry_type in [mood_check_in, stress_log, personal_reflection] then privacy_scope mustEqual private
          - if privacy_scope != private then consent_given mustEqual true
          - if timestamp missing, server sets now
          - when consent_given = true and consent_timestamp missing, server sets now
      JournalEntryUpdate:
        type: object
        properties:
          title: { type: string }
          subtitle: { type: string }
          content: { type: string }
          mood_rating: { type: integer, minimum: 1, maximum: 10 }
          mood_description: { type: string }
          stress_level: { type: integer, minimum: 1, maximum: 5 }
          energy_level: { type: integer, minimum: 1, maximum: 10 }
          stress_triggers: { type: array, items: { type: string } }
          coping_strategies: { type: array, items: { type: string } }
          gratitude_items: { type: array, items: { type: string } }
          daily_goals: { type: array, items: { type: string } }
          affirmations: { type: array, items: { type: string } }
          achievements: { type: array, items: { type: string } }
          learnings: { type: array, items: { type: string } }
          challenges: { type: array, items: { type: string } }
          location_site_name: { type: string }
          location_address: { type: string }
          location_coordinates:
            type: object
            properties:
              lat: { type: number, minimum: -90, maximum: 90 }
              lng: { type: number, minimum: -180, maximum: 180 }
            required: [lat, lng]
          location_area_type: { type: string }
          team_members: { type: array, items: { type: string } }
          tags: { type: array, items: { type: string } }
          priority: { type: string }
          severity: { type: string }
          completion_rate: { type: number, minimum: 0.0, maximum: 1.0 }
          efficiency_score: { type: number, minimum: 0.0, maximum: 10.0 }
          quality_score: { type: number, minimum: 0.0, maximum: 10.0 }
          items_processed: { type: integer, minimum: 0 }
          is_bookmarked: { type: boolean }
          is_draft: { type: boolean }
          privacy_scope: { type: string, enum: { $ref: '#/contract/enums/JournalPrivacyScope' } }
          sharing_permissions: { type: array, items: { type: integer } }
          metadata: { type: object }
        x-rules:
          - server increments version and last_sync_timestamp on update
      JournalEntryListItem:
        type: object
        properties:
          id: { type: string }
          title: { type: string }
          subtitle: { type: string }
          entry_type: { type: string }
          timestamp: { type: string, format: date-time }
          privacy_scope: { type: string }
          mood_rating: { type: integer, nullable: true }
          stress_level: { type: integer, nullable: true }
          energy_level: { type: integer, nullable: true }
          location_site_name: { type: string, nullable: true }
          is_bookmarked: { type: boolean }
          is_draft: { type: boolean }
          sync_status: { type: string }
          user_name: { type: string }
          media_count: { type: integer }
          wellbeing_summary:
            type: object
            nullable: true
            properties:
              mood: { type: string }
              stress: { type: string }
              energy: { type: string }
          created_at: { type: string }
          updated_at: { type: string }
      JournalEntryDetail:
        type: object
        properties:
          id: { type: string }
          title: { type: string }
          subtitle: { type: string }
          content: { type: string }
          entry_type: { type: string }
          timestamp: { type: string, format: date-time }
          duration_minutes: { type: integer, nullable: true }
          privacy_scope: { type: string }
          consent_given: { type: boolean }
          consent_timestamp: { type: string, nullable: true }
          sharing_permissions: { type: array, items: { type: integer } }
          mood_rating: { type: integer, nullable: true }
          mood_description: { type: string, nullable: true }
          stress_level: { type: integer, nullable: true }
          energy_level: { type: integer, nullable: true }
          stress_triggers: { type: array, items: { type: string } }
          coping_strategies: { type: array, items: { type: string } }
          gratitude_items: { type: array, items: { type: string } }
          daily_goals: { type: array, items: { type: string } }
          affirmations: { type: array, items: { type: string } }
          achievements: { type: array, items: { type: string } }
          learnings: { type: array, items: { type: string } }
          challenges: { type: array, items: { type: string } }
          location_site_name: { type: string, nullable: true }
          location_address: { type: string, nullable: true }
          location_coordinates:
            type: object
            nullable: true
            properties:
              lat: { type: number }
              lng: { type: number }
          location_area_type: { type: string, nullable: true }
          team_members: { type: array, items: { type: string } }
          tags: { type: array, items: { type: string } }
          priority: { type: string, nullable: true }
          severity: { type: string, nullable: true }
          completion_rate: { type: number, nullable: true }
          efficiency_score: { type: number, nullable: true }
          quality_score: { type: number, nullable: true }
          items_processed: { type: integer, nullable: true }
          is_bookmarked: { type: boolean }
          is_draft: { type: boolean }
          sync_status: { type: string }
          mobile_id: { type: string, nullable: true }
          version: { type: integer }
          last_sync_timestamp: { type: string, nullable: true }
          user_name: { type: string }
          is_wellbeing_entry: { type: boolean }
          has_wellbeing_metrics: { type: boolean }
          media_attachments:
            type: array
            items:
              type: object
              properties:
                id: { type: string }
                media_type: { type: string }
                file_url: { type: string, nullable: true }
                original_filename: { type: string }
                mime_type: { type: string, nullable: true }
                file_size: { type: integer, nullable: true }
                file_size_display: { type: string }
                caption: { type: string }
                display_order: { type: integer }
                is_hero_image: { type: boolean }
                mobile_id: { type: string, nullable: true }
                sync_status: { type: string }
                created_at: { type: string }
                updated_at: { type: string }
          created_at: { type: string }
          updated_at: { type: string }
          metadata: { type: object }
      JournalSearchRequest:
        type: object
        required: [query]
        properties:
          query: { type: string, maxLength: 500 }
          entry_types: { type: array, items: { type: string } }
          date_from: { type: string, format: date-time }
          date_to: { type: string, format: date-time }
          mood_min: { type: integer, minimum: 1, maximum: 10 }
          mood_max: { type: integer, minimum: 1, maximum: 10 }
          stress_min: { type: integer, minimum: 1, maximum: 5 }
          stress_max: { type: integer, minimum: 1, maximum: 5 }
          location: { type: string, maxLength: 200 }
          tags: { type: array, items: { type: string } }
          sort_by:
            type: string
            enum: [relevance, timestamp, -timestamp, mood_rating, stress_level]
        x-rules:
          - if date_from and date_to then date_from <= date_to
          - if mood_min and mood_max then mood_min <= mood_max
          - if stress_min and stress_max then stress_min <= stress_max
      JournalSyncRequest:
        type: object
        required: [entries]
        properties:
          entries:
            type: array
            items:
              type: object
              required: [mobile_id, timestamp, entry_type, title]
              properties:
                mobile_id: { type: string }
                version: { type: integer }
                timestamp: { type: string, format: date-time }
                entry_type: { type: string }
                title: { type: string }
                ...: { type: string }
          last_sync_timestamp: { type: string, format: date-time }
          client_id: { type: string }
      JournalSyncResponse:
        type: object
        properties:
          sync_timestamp: { type: string }
          created_count: { type: integer }
          updated_count: { type: integer }
          conflict_count: { type: integer }
          created_entries:
            type: array
            items: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
          updated_entries:
            type: array
            items: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
          conflicts:
            type: array
            items:
              type: object
              properties:
                status: { type: string, enum: [conflict, error, updated] }
                mobile_id: { type: string }
                client_version: { type: integer, nullable: true }
                server_version: { type: integer, nullable: true }
                server_entry: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
                errors: { type: object }
          server_changes:
            type: array
            items: { type: object }
      JournalPrivacySettings:
        type: object
        properties:
          default_privacy_scope: { type: string, enum: { $ref: '#/contract/enums/JournalPrivacyScope' } }
          wellbeing_sharing_consent: { type: boolean }
          manager_access_consent: { type: boolean }
          analytics_consent: { type: boolean }
          crisis_intervention_consent: { type: boolean }
          data_retention_days: { type: integer, minimum: 30, maximum: 3650 }
          auto_delete_enabled: { type: boolean }
      WellnessContentListItem:
        type: object
        properties:
          id: { type: string }
          title: { type: string }
          summary: { type: string }
          category: { type: string, enum: { $ref: '#/contract/enums/WellnessContentCategory' } }
          delivery_context: { type: string, enum: { $ref: '#/contract/enums/WellnessDeliveryContext' } }
          content_level: { type: string, enum: { $ref: '#/contract/enums/WellnessContentLevel' } }
          evidence_level: { type: string, enum: { $ref: '#/contract/enums/EvidenceLevel' } }
          is_high_evidence: { type: boolean }
          needs_verification: { type: boolean }
          workplace_specific: { type: boolean }
          field_worker_relevant: { type: boolean }
          priority_score: { type: integer, minimum: 1, maximum: 100 }
          estimated_reading_time: { type: integer, minimum: 1 }
          complexity_score: { type: integer, minimum: 1, maximum: 5 }
          is_active: { type: boolean }
          interaction_count: { type: integer }
          created_at: { type: string }
          updated_at: { type: string }
      WellnessContentDetail:
        type: object
        properties:
          id: { type: string }
          title: { type: string }
          summary: { type: string }
          content: { type: string }
          category: { type: string }
          delivery_context: { type: string }
          content_level: { type: string }
          evidence_level: { type: string }
          tags: { type: array, items: { type: string } }
          trigger_patterns: { type: object }
          workplace_specific: { type: boolean }
          field_worker_relevant: { type: boolean }
          action_tips: { type: array, items: { type: string } }
          key_takeaways: { type: array, items: { type: string } }
          related_topics: { type: array, items: { type: string } }
          source_name: { type: string }
          source_url: { type: string, nullable: true }
          evidence_summary: { type: string, nullable: true }
          citations: { type: array, items: { type: string } }
          last_verified_date: { type: string }
          is_active: { type: boolean }
          priority_score: { type: integer }
          seasonal_relevance: { type: array, items: { type: integer, minimum: 1, maximum: 12 } }
          frequency_limit_days: { type: integer }
          estimated_reading_time: { type: integer }
          complexity_score: { type: integer }
          content_version: { type: string }
          created_by: { type: string, nullable: true }
          created_at: { type: string }
          updated_at: { type: string }
          effectiveness_metrics:
            type: object
            properties:
              total_interactions: { type: integer }
              effectiveness_score: { type: number }
              avg_rating: { type: number, nullable: true }
              completion_rate: { type: number }
      WellnessInteractionCreate:
        type: object
        required: [content, interaction_type, delivery_context]
        properties:
          content: { type: string }
          interaction_type: { type: string, enum: { $ref: '#/contract/enums/WellnessInteractionType' } }
          delivery_context: { type: string, enum: { $ref: '#/contract/enums/WellnessDeliveryContext' } }
          time_spent_seconds: { type: integer, minimum: 0 }
          completion_percentage: { type: integer, minimum: 0, maximum: 100 }
          user_rating: { type: integer, minimum: 1, maximum: 5 }
          user_feedback: { type: string }
          action_taken: { type: boolean }
          trigger_journal_entry: { type: string }
          user_mood_at_delivery: { type: integer, minimum: 1, maximum: 10 }
          user_stress_at_delivery: { type: integer, minimum: 1, maximum: 5 }
          metadata: { type: object }
      DailyTipRequest:
        type: object
        properties:
          preferred_category: { type: string, enum: { $ref: '#/contract/enums/WellnessContentCategory' } }
          content_level: { type: string, enum: { $ref: '#/contract/enums/WellnessContentLevel' } }
          exclude_recent: { type: boolean, default: true }
      DailyTipResponse:
        type: object
        properties:
          daily_tip: { $ref: '#/contract/components/schemas/WellnessContentDetail' }
          personalization_metadata: { type: object }
          next_tip_available_at: { type: string, format: date-time }
          interaction_id: { type: string }
      ContextualContentRequest:
        type: object
        required: [journal_entry]
        properties:
          journal_entry:
            type: object
            required: [entry_type, timestamp]
            properties:
              entry_type: { type: string }
              timestamp: { type: string, format: date-time }
              mood_rating: { type: integer, minimum: 1, maximum: 10 }
              stress_level: { type: integer, minimum: 1, maximum: 5 }
              content: { type: string }
          user_context: { type: object }
          max_content_items: { type: integer, minimum: 1, maximum: 10, default: 3 }
      PersonalizedRequest:
        type: object
        properties:
          limit: { type: integer, minimum: 1, maximum: 20, default: 5 }
          categories: { type: array, items: { type: string, enum: { $ref: '#/contract/enums/WellnessContentCategory' } } }
          exclude_viewed: { type: boolean, default: true }
          diversity_enabled: { type: boolean, default: true }
      OnboardingConversationStart:
        type: object
        properties:
          initial_input: { type: string }
          language: { type: string, default: en }
          client_context: { type: object }
          resume_existing: { type: boolean, default: false }
      OnboardingConversationProcess:
        type: object
        required: [user_input]
        properties:
          user_input: { type: string }
          context: { type: object }
    websocket:
      mobile_sync:
        endpoint: /ws/mobile/sync/
        auth: session_cookie
        url_params:
          - device_id
        client_messages:
          start_sync:
            type: object
            required: [type, sync_id]
            properties:
              type: { const: start_sync }
              sync_id: { type: string }
              data_types: { type: array, items: { type: string } }
              total_items: { type: integer }
          sync_data:
            type: object
            required: [type, sync_id, data]
            properties:
              type: { const: sync_data }
              sync_id: { type: string }
              data:
                type: object
                properties:
                  voice_data:
                    type: object
                    properties:
                      verified: { type: boolean }
                      confidence_score: { type: number }
                      quality_score: { type: number }
                      processing_time_ms: { type: integer }
                  behavioral_data: { type: object, additionalProperties: true }
                  sessions: { type: object, additionalProperties: true }
                  metrics:
                    type: object
                    properties:
                      cpu_usage: { type: number }
                      memory_usage: { type: number }
                      network_latency: { type: integer }
          request_server_data:
            type: object
            required: [type, request_type]
            properties:
              type: { const: request_server_data }
              request_type: { type: string, enum: [all, voice, behavioral, sessions] }
              since_timestamp: { type: string, format: date-time }
              request_id: { type: string }
          resolve_conflict:
            type: object
            required: [type, conflict_id, resolution_strategy]
            properties:
              type: { const: resolve_conflict }
              conflict_id: { type: string }
              resolution_strategy: { type: string }
              resolved_data: { type: object }
          subscribe_events:
            type: object
            required: [type, event_types]
            properties:
              type: { const: subscribe_events }
              event_types: { type: array, items: { type: string } }
          heartbeat:
            type: object
            required: [type]
            properties:
              type: { const: heartbeat }
              client_time: { type: string, format: date-time }
          device_status:
            type: object
            required: [type, status]
            properties:
              type: { const: device_status }
              status: { type: string }
              device_info:
                type: object
                properties:
                  app_version: { type: string }
                  os_version: { type: string }
                  device_model: { type: string }
        server_messages:
          connection_established:
            properties:
              type: { const: connection_established }
              user_id: { type: string }
              device_id: { type: string }
              server_time: { type: string, format: date-time }
              features:
                type: object
                properties:
                  real_time_sync: { type: boolean }
                  push_notifications: { type: boolean }
                  bi_directional_sync: { type: boolean }
                  conflict_resolution: { type: boolean }
          sync_session_started:
            properties:
              type: { const: sync_session_started }
              sync_id: { type: string }
              server_time: { type: string }
              session_info:
                type: object
                properties:
                  supported_data_types:
                    type: array
                    items: { type: string, enum: [voice, behavioral, session, metrics] }
                  max_batch_size: { type: integer }
                  timeout_seconds: { type: integer }
          sync_progress:
            properties:
              type: { const: sync_progress }
              sync_id: { type: string }
              progress:
                type: object
                properties:
                  synced_items: { type: integer }
                  failed_items: { type: integer }
                  total_items: { type: integer }
          server_data_response:
            properties:
              type: { const: server_data_response }
              request_id: { type: string }
              data: { type: object }
              server_timestamp: { type: string }
          heartbeat_response:
            properties:
              type: { const: heartbeat_response }
              server_time: { type: string }
              client_time: { type: string }
          server_heartbeat:
            properties:
              type: { const: server_heartbeat }
              server_time: { type: string }
              connection_duration: { type: number }
          error:
            properties:
              type: { const: error }
              error_code: { type: string }
              message: { type: string }
              timestamp: { type: string }
  endpoints:
    # Journal
    - id: journal_list
      method: GET
      path: /api/v1/journal/api/entries/
      auth: session_cookie
      query:
        entry_types[]: string
        date_from: date-time
        date_to: date-time
        mood_min: integer
        mood_max: integer
        stress_min: integer
        stress_max: integer
        location: string
        tags[]: string
      responses:
        200:
          type: array
          items: { $ref: '#/contract/components/schemas/JournalEntryListItem' }
    - id: journal_create
      method: POST
      path: /api/v1/journal/api/entries/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/JournalEntryCreate' }
      responses:
        201: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
    - id: journal_detail
      method: GET
      path: /api/v1/journal/api/entries/{id}/
      auth: session_cookie
      responses:
        200: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
    - id: journal_update
      method: PATCH
      path: /api/v1/journal/api/entries/{id}/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/JournalEntryUpdate' }
      responses:
        200: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
    - id: journal_delete
      method: DELETE
      path: /api/v1/journal/api/entries/{id}/
      auth: session_cookie+csrf
      responses:
        204: {}
    - id: journal_bulk_create
      method: POST
      path: /api/v1/journal/api/entries/bulk_create/
      auth: session_cookie+csrf
      request:
        type: object
        required: [entries]
        properties:
          entries:
            type: array
            items: { $ref: '#/contract/components/schemas/JournalEntryCreate' }
      responses:
        200:
          type: object
          properties:
            created_count: { type: integer }
            error_count: { type: integer }
            created_entries:
              type: array
              items: { $ref: '#/contract/components/schemas/JournalEntryDetail' }
            errors:
              type: array
              items: { type: object }
    - id: journal_search
      method: POST
      path: /api/v1/journal/api/search/
      auth: session_cookie
      request: { $ref: '#/contract/components/schemas/JournalSearchRequest' }
      responses:
        200: { type: object }
    - id: journal_analytics
      method: GET
      path: /api/v1/journal/api/analytics/
      auth: session_cookie
      query:
        user_id: string
        days: integer
      responses:
        200: { type: object }
    - id: journal_sync
      method: POST
      path: /api/v1/journal/api/sync/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/JournalSyncRequest' }
      responses:
        200: { $ref: '#/contract/components/schemas/JournalSyncResponse' }
    - id: journal_privacy_settings_get
      method: GET
      path: /api/v1/journal/api/privacy-settings/
      auth: session_cookie
      responses:
        200: { $ref: '#/contract/components/schemas/JournalPrivacySettings' }
    - id: journal_privacy_settings_put
      method: PUT
      path: /api/v1/journal/api/privacy-settings/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/JournalPrivacySettings' }
      responses:
        200: { $ref: '#/contract/components/schemas/JournalPrivacySettings' }

    # Wellness
    - id: wellness_content_list
      method: GET
      path: /api/v1/wellness/api/content/
      auth: session_cookie
      query:
        category: string
        evidence_level: string
        content_level: string
        workplace_specific: boolean
        field_worker_relevant: boolean
        high_evidence: boolean
      responses:
        200:
          type: array
          items: { $ref: '#/contract/components/schemas/WellnessContentListItem' }
    - id: wellness_content_detail
      method: GET
      path: /api/v1/wellness/api/content/{id}/
      auth: session_cookie
      responses:
        200: { $ref: '#/contract/components/schemas/WellnessContentDetail' }
    - id: wellness_track_interaction
      method: POST
      path: /api/v1/wellness/api/content/{id}/track_interaction/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/WellnessInteractionCreate' }
      responses:
        201:
          type: object
          properties:
            interaction_id: { type: string }
            engagement_score: { type: integer }
            message: { type: string }
    - id: wellness_categories
      method: GET
      path: /api/v1/wellness/api/content/categories/
      auth: session_cookie
      responses:
        200: { type: object }
    - id: wellness_daily_tip
      method: GET
      path: /api/v1/wellness/api/daily-tip/
      auth: session_cookie
      query:
        preferred_category: string
        content_level: string
        exclude_recent: boolean
      responses:
        200: { $ref: '#/contract/components/schemas/DailyTipResponse' }
    - id: wellness_contextual
      method: POST
      path: /api/v1/wellness/api/contextual/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/ContextualContentRequest' }
      responses:
        200: { type: object }
    - id: wellness_personalized
      method: GET
      path: /api/v1/wellness/api/personalized/
      auth: session_cookie
      query:
        limit: integer
        categories[]: string
        exclude_viewed: boolean
        diversity_enabled: boolean
      responses:
        200: { type: object }
    - id: wellness_progress_get
      method: GET
      path: /api/v1/wellness/api/progress/
      auth: session_cookie
      responses:
        200: { type: object }
    - id: wellness_progress_put
      method: PUT
      path: /api/v1/wellness/api/progress/
      auth: session_cookie+csrf
      request: { type: object }
      responses:
        200: { type: object }

    # Onboarding (selected)
    - id: onboarding_conversation_start
      method: POST
      path: /api/v1/onboarding/conversation/start/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/OnboardingConversationStart' }
      responses:
        200: { type: object }
        403: { type: object }
    - id: onboarding_conversation_process
      method: POST
      path: /api/v1/onboarding/conversation/{conversation_id}/process/
      auth: session_cookie+csrf
      request: { $ref: '#/contract/components/schemas/OnboardingConversationProcess' }
      responses:
        200: { type: object }
        202:
          type: object
          properties:
            status: { type: string, enum: [processing] }
            status_url: { type: string }
            task_id: { type: string }
            task_status_url: { type: string }
    - id: onboarding_conversation_status
      method: GET
      path: /api/v1/onboarding/conversation/{conversation_id}/status/
      auth: session_cookie
      responses:
        200: { type: object }

    # Read-only service sync (selected)
    - id: service_people
      method: GET
      path: /api/v1/people/
      auth: session_cookie
      query:
        last_update: string
      responses:
        200: { type: array, items: { type: object } }
    - id: service_peopleevents
      method: GET
      path: /api/v1/peopleevents/
      auth: session_cookie
      query:
        last_update: string
      responses:
        200: { type: array, items: { type: object } }

  frontend_asks:
    - Maintain session cookies (sessionid, csrftoken) and send X-CSRFToken for unsafe REST methods.
    - WebSocket handshake must include device_id and session cookies; send start_sync before sync_data, obey implied batch size (100).
    - Enforce journal validations: mood(1–10), stress(1–5), energy(1–10), completion_rate(0–1); private scope for sensitive wellbeing entry types; consent for non-private entries.
    - Include mobile_id and version in client sync payloads; handle conflicts by reconciling with server_version.
    - Track wellness interactions after content consumption; provide optional mood/stress at delivery.
    - Handle 202 async onboarding responses and poll provided status URLs.
    - Backoff/retry on transient WS/HTTP errors; handle structured WS error messages.
```

