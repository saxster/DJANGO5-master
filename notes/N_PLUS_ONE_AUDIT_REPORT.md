================================================================================
N+1 QUERY AUDIT REPORT
================================================================================

SUMMARY
--------------------------------------------------------------------------------
Files scanned: 716
Files with violations: 203
Total violations found: 1002
Optimized queries found: 103

VIOLATIONS BY SEVERITY
--------------------------------------------------------------------------------
HIGH: 66
MEDIUM: 936

DETAILED VIOLATIONS
--------------------------------------------------------------------------------

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/api/views.py:232
Type: missing_optimization
Code: thresholds = AdaptiveThreshold.objects.all().order_by('metric_name')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/exports.py:370
Type: missing_optimization
Code: thresholds = AdaptiveThreshold.objects.all().order_by('metric_name')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/exports.py:619
Type: missing_optimization
Code: thresholds = AdaptiveThreshold.objects.all().order_by('metric_name')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/update_thresholds.py:335
Type: missing_optimization
Code: thresholds = AdaptiveThreshold.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:374
Type: missing_optimization
Code: gaps = TestCoverageGap.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_manager.py:133
Type: missing_optimization
Code: queryset = self.model.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:582
Type: missing_optimization
Code: capabilities = list(Capability.objects.all().values('id', 'capname', 'parent_id'))

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/warm_caches.py:341
Type: missing_optimization
Code: Capability.objects.all().values(

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/services/query_service.py:154
Type: missing_optimization
Code: queryset = model_class.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/services/query_service.py:236
Type: missing_optimization
Code: queryset = model_class.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/query_optimization.py:302
Type: missing_optimization
Code: queryset=MyModel.objects.all(),

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/query_optimizer.py:20
Type: missing_optimization
Code: suggestions = optimizer.analyze_queryset(MyModel.objects.all())

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/query_optimizer.py:396
Type: missing_optimization
Code: suggestions = suggest_optimizations(MyModel.objects.all())

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/query_optimizer.py:404
Type: missing_optimization
Code: queryset = model_or_queryset.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:435
Type: missing_optimization
Code: nav_recs = NavigationRecommendation.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:436
Type: missing_optimization
Code: content_recs = ContentRecommendation.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/admin.py:23
Type: admin_without_select_related
Code: JournalEntryAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:67
Type: missing_optimization
Code: tenants = list(Tenant.objects.all())

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/mqtt_integration.py:554
Type: missing_optimization
Code: for tenant in Tenant.objects.all():

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/search.py:903
Type: missing_optimization
Code: for tenant in Tenant.objects.all():

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/code_quality.py:138
Type: missing_optimization
Code: models = DjangoModel.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/performance_analyzer.py:117
Type: missing_optimization
Code: models = DjangoModel.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/codemods/performance_codemods.py:69
Type: missing_optimization
Code: # Check for Model.objects.all(), filter(), etc.

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/generators/doc_generator.py:48
Type: missing_optimization
Code: models = DjangoModel.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/generators/doc_generator.py:345
Type: missing_optimization
Code: definitions = GraphQLDefinition.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/indexers/embeddings_indexer.py:380
Type: missing_optimization
Code: indexed_files = IndexedFile.objects.all()[:max_files]

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/indexers/incremental_indexer.py:466
Type: missing_optimization
Code: IndexedFile.objects.all().delete()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/tests/base.py:53
Type: missing_optimization
Code: model.objects.all().delete()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/tests/base.py:316
Type: missing_optimization
Code: users = User.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:177
Type: admin_without_select_related
Code: TaAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:415
Type: admin_without_select_related
Code: BtAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:500
Type: admin_without_select_related
Code: ShiftAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:1377
Type: admin_without_select_related
Code: LLMRecommendationAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:1547
Type: admin_without_select_related
Code: AIChangeRecordAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:125
Type: missing_optimization
Code: label="Belongs to", required=False, queryset=obm.Bt.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/utils.py:65
Type: missing_optimization
Code: return TypeAssist.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:62
Type: admin_without_select_related
Code: PeopleConversationalOnboardingAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:289
Type: admin_without_select_related
Code: TenantConversationalOnboardingAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:109
Type: admin_without_select_related
Code: ExperimentAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:295
Type: admin_without_select_related
Code: ExperimentAssignmentAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:344
Type: missing_optimization
Code: experiments = Experiment.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:499
Type: missing_optimization
Code: profiles = PreferenceProfile.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:104
Type: missing_optimization
Code: documents = AuthoritativeKnowledge.objects.all().order_by('-cdtz')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:75
Type: missing_optimization
Code: sources = KnowledgeSource.objects.all().order_by('-cdtz')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:272
Type: missing_optimization
Code: jobs = KnowledgeIngestionJob.objects.all().order_by('-cdtz')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:777
Type: missing_optimization
Code: sources = KnowledgeSource.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:795
Type: missing_optimization
Code: jobs = KnowledgeIngestionJob.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:821
Type: missing_optimization
Code: reviews = KnowledgeReview.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/management/commands/seed_knowledge_base.py:27
Type: missing_optimization
Code: AuthoritativeKnowledge.objects.all().delete()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views.py:1013
Type: missing_optimization
Code: queryset = AIChangeSet.objects.all().order_by('-cdtz')

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views.py:1075
Type: missing_optimization
Code: queryset = AuthoritativeKnowledge.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views_phase2.py:331
Type: missing_optimization
Code: queryset = AuthoritativeKnowledge.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:278
Type: admin_without_select_related
Code: PeopleAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:419
Type: admin_without_select_related
Code: GroupAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:524
Type: admin_without_select_related
Code: PgbelongingAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:579
Type: admin_without_select_related
Code: CapabilityAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:508
Type: missing_optimization
Code: self.fields["checklist"].choices = QuestionSet.objects.all().values_list(

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/rest_service/views.py:18
Type: missing_optimization
Code: queryset = model.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/schema.py:74
Type: missing_optimization
Code: return Tracking.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/schema.py:78
Type: missing_optimization
Code: objs = TestGeo.objects.all()

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/admin.py:16
Type: admin_without_select_related
Code: TestScenarioAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/admin.py:16
Type: admin_without_select_related
Code: WellnessContentAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/admin.py:170
Type: admin_without_select_related
Code: WellnessUserProgressAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/admin.py:291
Type: admin_without_select_related
Code: WellnessContentInteractionAdmin

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/management/commands/seed_wellness_content.py:93
Type: missing_optimization
Code: return list(Tenant.objects.all())

[HIGH] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services/work_order_service.py:508
Type: missing_optimization
Code: queryset = Wom.objects.all()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/asset_admin.py:711
Type: missing_optimization
Code: if not Asset.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/location_admin.py:248
Type: missing_optimization
Code: if not Location.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:890
Type: missing_optimization
Code: existing_records = model.objects.filter(**{f"{lookup_field}__in": values})

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:929
Type: missing_optimization
Code: existing_records = model.objects.filter(**{f"{lookup_field}__in": values})

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:989
Type: missing_optimization
Code: return self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:1007
Type: missing_optimization
Code: return self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:1622
Type: missing_optimization
Code: if not Question.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:1845
Type: missing_optimization
Code: if not QuestionSetBelonging.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:2023
Type: missing_optimization
Code: model.objects.filter(**{f"{model_field}": val}).values()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/admin/question_admin.py:2026
Type: missing_optimization
Code: count = model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:85
Type: missing_optimization
Code: self.fields["parent"].queryset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:88
Type: missing_optimization
Code: self.fields["location"].queryset = Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:91
Type: missing_optimization
Code: self.fields["type"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:94
Type: missing_optimization
Code: self.fields["category"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:98
Type: missing_optimization
Code: self.fields["subcategory"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:102
Type: missing_optimization
Code: self.fields["unit"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:106
Type: missing_optimization
Code: self.fields["brand"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:110
Type: missing_optimization
Code: self.fields["servprov"].queryset = om.Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:146
Type: missing_optimization
Code: and Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:185
Type: missing_optimization
Code: and Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:420
Type: missing_optimization
Code: self.fields["parent"].queryset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:423
Type: missing_optimization
Code: self.fields["type"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:505
Type: missing_optimization
Code: self.fields["location"].queryset = Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:508
Type: missing_optimization
Code: self.fields["parent"].queryset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/asset_form.py:511
Type: missing_optimization
Code: self.fields["type"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/location_form.py:56
Type: missing_optimization
Code: self.fields["parent"].queryset = Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/location_form.py:59
Type: missing_optimization
Code: self.fields["type"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/location_form.py:93
Type: missing_optimization
Code: and Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/location_form.py:122
Type: missing_optimization
Code: and Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_condition_form.py:91
Type: missing_optimization
Code: parent_q = QuestionSetBelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:212
Type: missing_optimization
Code: self.fields['site_type_includes'].choices = om.TypeAssist.objects.filter(Q(tatype__tacode = "SITETYPE") | Q(tacode='NONE'), client_id = self.request.session['client_id']).values_list('id', 'taname')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:215
Type: missing_optimization
Code: self.fields['site_grp_includes'].choices = pm.Pgroup.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:351
Type: missing_optimization
Code: parent_qsb = QuestionSetBelonging.objects.filter(pk=parent_id).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:536
Type: missing_optimization
Code: self.fields["site_type_includes"].choices = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:547
Type: missing_optimization
Code: self.fields["site_grp_includes"].choices = pm.Pgroup.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/forms/question_form.py:583
Type: missing_optimization
Code: self.fields['site_type_includes'].choices = om.TypeAssist.objects.filter(Q(tatype__tacode='SITETYPE', client_id=S['client_id']) | Q(tacode='NONE')).values_list('id', 'tacode')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/management/commands/setup_question_conditions.py:34
Type: missing_optimization
Code: questions = QuestionSetBelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager.py:150
Type: missing_optimization
Code: Location.objects.filter(common_filter)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:51
Type: missing_optimization
Code: qsets = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:59
Type: missing_optimization
Code: qsets = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:91
Type: missing_optimization
Code: qsets = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:314
Type: missing_optimization
Code: assets_query = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:363
Type: missing_optimization
Code: query = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:453
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/asset_manager_orm_optimized.py:483
Type: missing_optimization
Code: metrics = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/attachment_manager.py:69
Type: missing_optimization
Code: detail_uuids = JobneedDetails.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/attachment_manager.py:93
Type: missing_optimization
Code: ta = TypeAssist.objects.filter(taname=R["ownername"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/attachment_manager.py:147
Type: missing_optimization
Code: PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/attachment_manager.py:172
Type: missing_optimization
Code: People.objects.filter(id=eventlogqset.first()["people_id"]).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:477
Type: missing_optimization
Code: Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:567
Type: missing_optimization
Code: atts = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:692
Type: missing_optimization
Code: checkpoint_attachments = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:699
Type: missing_optimization
Code: details = JobneedDetails.objects.filter(jobneed_id=item['id']).values_list('uuid', flat=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:701
Type: missing_optimization
Code: detail_attachments += Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:753
Type: missing_optimization
Code: jnd_uuids = JobneedDetails.objects.filter(jobneed_id=id).values_list('uuid', flat=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:1214
Type: missing_optimization
Code: group_ids = pm.Pgbelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:1250
Type: missing_optimization
Code: group_ids = pm.Pgbelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:1343
Type: missing_optimization
Code: attachment_count = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager.py:1388
Type: missing_optimization
Code: attachment_count = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager_orm_optimized.py:260
Type: missing_optimization
Code: emails = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager_orm_optimized.py:638
Type: missing_optimization
Code: active_people = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/job_manager_orm_optimized.py:645
Type: missing_optimization
Code: bu_obj = Bt.objects.filter(id=bu_id).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/question_manager.py:284
Type: missing_optimization
Code: has_questions = QuestionSetBelonging.objects.filter(qset=OuterRef("pk")).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/question_manager.py:437
Type: missing_optimization
Code: site_groups = pm.Pgbelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/managers/question_manager.py:445
Type: missing_optimization
Code: qset_ids = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/services/question_service.py:74
Type: missing_optimization
Code: row_data = Question.objects.filter(id=question.id).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/services/question_service.py:143
Type: missing_optimization
Code: row_data = Question.objects.filter(id=question.id).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/services/question_service.py:197
Type: missing_optimization
Code: if QuestionSetBelonging.objects.filter(question=question).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/signals.py:43
Type: missing_optimization
Code: AssetLog.objects.filter(asset_id=instance.id).order_by("-cdtz").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/utils.py:31
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/utils.py:47
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/utils.py:426
Type: missing_optimization
Code: objects = model.objects.filter(bu=request.session["bu_id"], **kwargs).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/utils_orm.py:26
Type: missing_optimization
Code: ticket = Ticket.objects.filter(ticketno=ticketno).values('events').first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:38
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:48
Type: missing_optimization
Code: QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:63
Type: missing_optimization
Code: QuestionSetBelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:97
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:107
Type: missing_optimization
Code: QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/asset/comparison_views.py:119
Type: missing_optimization
Code: QuestionSetBelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:46
Type: missing_optimization
Code: res = P["model"].objects.filter(id=R["id"]).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:50
Type: missing_optimization
Code: model.objects.filter(uuid=R["ownerid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:52
Type: missing_optimization
Code: .objects.filter(owner=R["ownerid"])

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:86
Type: missing_optimization
Code: model.objects.filter(uuid=R["ownerid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:148
Type: missing_optimization
Code: get_people = Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/attachment_views.py:155
Type: missing_optimization
Code: obm.GeofenceMaster.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/activity/views/question_views.py:169
Type: missing_optimization
Code: row_data = Question.objects.filter(id=ques.id).values(*self.params["fields"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/api/views.py:189
Type: missing_optimization
Code: prediction = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/api/views.py:259
Type: missing_optimization
Code: patterns = TestCoveragePattern.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/api/views.py:317
Type: missing_optimization
Code: recent_7d = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/api/views.py:322
Type: missing_optimization
Code: implemented_count = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:50
Type: missing_optimization
Code: total_gaps = CoverageGap.objects.filter(status=CoverageGapStatus.IDENTIFIED).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:53
Type: missing_optimization
Code: priority_counts = CoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:60
Type: missing_optimization
Code: recent_gaps = CoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:66
Type: missing_optimization
Code: critical_gaps = CoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:82
Type: missing_optimization
Code: latest_prediction = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:112
Type: missing_optimization
Code: recent_updates = AdaptiveThreshold.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:117
Type: missing_optimization
Code: stale_thresholds = AdaptiveThreshold.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/dashboard_integration.py:139
Type: missing_optimization
Code: recent_runs = TestRun.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/exports.py:301
Type: missing_optimization
Code: patterns = TestCoveragePattern.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/exports.py:432
Type: missing_optimization
Code: predictions = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/exports.py:594
Type: missing_optimization
Code: patterns = TestCoveragePattern.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:154
Type: missing_optimization
Code: coverage_gaps = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:166
Type: missing_optimization
Code: patterns = TestCoveragePattern.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:170
Type: missing_optimization
Code: thresholds = AdaptiveThreshold.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:271
Type: missing_optimization
Code: previous_gaps = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:276
Type: missing_optimization
Code: previous_runs = TestRun.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/ai_insights_report.py:281
Type: missing_optimization
Code: previous_anomalies = AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/generate_tests.py:93
Type: missing_optimization
Code: gaps = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/update_thresholds.py:155
Type: missing_optimization
Code: test_runs = TestRun.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/update_thresholds.py:160
Type: missing_optimization
Code: stream_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/update_thresholds.py:164
Type: missing_optimization
Code: anomaly_occurrences = AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/management/commands/update_thresholds.py:421
Type: missing_optimization
Code: stale_thresholds = AdaptiveThreshold.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/adaptive_thresholds.py:255
Type: missing_optimization
Code: return cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:259
Type: missing_optimization
Code: return cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:277
Type: missing_optimization
Code: new_baselines = cls.objects.filter(created_at__gte=since_date).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:280
Type: missing_optimization
Code: superseded = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:287
Type: missing_optimization
Code: cls.objects.filter(created_at__gte=since_date)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:294
Type: missing_optimization
Code: high_confidence = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:299
Type: missing_optimization
Code: total_recent = cls.objects.filter(created_at__gte=since_date).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/ml_baselines.py:534
Type: missing_optimization
Code: validated_comparisons = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/regression_predictions.py:210
Type: missing_optimization
Code: predictions = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/regression_predictions.py:241
Type: missing_optimization
Code: return cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/regression_predictions.py:252
Type: missing_optimization
Code: validated_predictions = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/regression_predictions.py:371
Type: missing_optimization
Code: return cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/models/regression_predictions.py:381
Type: missing_optimization
Code: metrics = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/adaptive_threshold_updater.py:160
Type: missing_optimization
Code: events_query = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/adaptive_threshold_updater.py:218
Type: missing_optimization
Code: runs = TestRun.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/adaptive_threshold_updater.py:232
Type: missing_optimization
Code: runs = TestRun.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/adaptive_threshold_updater.py:252
Type: missing_optimization
Code: window_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/adaptive_threshold_updater.py:692
Type: missing_optimization
Code: related_anomalies = AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/pattern_analyzer.py:43
Type: missing_optimization
Code: anomaly_signatures = AnomalySignature.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/pattern_analyzer.py:345
Type: missing_optimization
Code: existing_gap = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:144
Type: missing_optimization
Code: recent_anomalies_7d = AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:147
Type: missing_optimization
Code: recent_anomalies_30d = AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:213
Type: missing_optimization
Code: stream_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:282
Type: missing_optimization
Code: anomalies = AnomalyOccurrence.objects.filter(created_at__gte=since_date)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:309
Type: missing_optimization
Code: resolved_gaps = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:317
Type: missing_optimization
Code: 'visual_test_count': float(TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:320
Type: missing_optimization
Code: 'performance_test_count': float(TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:496
Type: missing_optimization
Code: recent_signatures = AnomalySignature.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:655
Type: missing_optimization
Code: existing = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/services/regression_predictor.py:734
Type: missing_optimization
Code: predictions = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/tasks.py:261
Type: missing_optimization
Code: dismissed_gaps = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/tasks.py:269
Type: missing_optimization
Code: old_patterns = TestCoveragePattern.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/tasks.py:277
Type: missing_optimization
Code: old_predictions = RegressionPrediction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:236
Type: missing_optimization
Code: recent_generations = TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:243
Type: missing_optimization
Code: 'total_generated': TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:246
Type: missing_optimization
Code: 'pending_implementation': TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:249
Type: missing_optimization
Code: 'implemented': TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/ai_testing/views.py:253
Type: missing_optimization
Code: TestCoverageGap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/dataloaders.py:251
Type: missing_optimization
Code: counts = self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:362
Type: missing_optimization
Code: 'active': People.objects.filter(is_active=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:363
Type: missing_optimization
Code: 'recent': People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:369
Type: missing_optimization
Code: 'active': Pgroup.objects.filter(is_active=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:373
Type: missing_optimization
Code: 'active': Asset.objects.filter(is_active=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:377
Type: missing_optimization
Code: 'pending': Job.objects.filter(status='pending').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/graphql/enhanced_schema.py:378
Type: missing_optimization
Code: 'completed': Job.objects.filter(status='completed').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/mobile_consumers.py:529
Type: missing_optimization
Code: logs = VoiceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/api/mobile_consumers.py:534
Type: missing_optimization
Code: logs = VoiceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:80
Type: missing_optimization
Code: total_ai_verifications = atdm.PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:86
Type: missing_optimization
Code: successful_verifications = atdm.PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:95
Type: missing_optimization
Code: fraud_detections = atdm.PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:109
Type: missing_optimization
Code: active_profiles = UserBehaviorProfile.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:115
Type: missing_optimization
Code: prev_week_verifications = atdm.PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:441
Type: missing_optimization
Code: recent_logs = FaceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:482
Type: missing_optimization
Code: return UserBehaviorProfile.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_analytics_dashboard.py:491
Type: missing_optimization
Code: return AnomalyDetectionResult.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_enhanced_views.py:453
Type: missing_optimization
Code: lambda: atdm.PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_enhanced_views.py:623
Type: missing_optimization
Code: lambda: list(BehavioralEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ai_enhanced_views.py:742
Type: missing_optimization
Code: lambda: FaceEmbedding.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/managers.py:36
Type: missing_optimization
Code: valid_attachments = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/managers.py:144
Type: missing_optimization
Code: get_people = Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/managers.py:149
Type: missing_optimization
Code: GeofenceMaster.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/managers.py:198
Type: missing_optimization
Code: all_shifts_under_site = Shift.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/managers.py:224
Type: missing_optimization
Code: if atts := Attachment.objects.filter(owner=qset[0]["uuid"]).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ticket_integration.py:172
Type: missing_optimization
Code: categories = TypeAssist.objects.filter(tacode__in=category_codes)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ticket_integration.py:176
Type: missing_optimization
Code: categories = TypeAssist.objects.filter(tacode__in=cls.ATTENDANCE_CATEGORIES.keys())

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ticket_integration.py:179
Type: missing_optimization
Code: tickets_to_resolve = Ticket.objects.filter(**query_filters)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/ticket_integration.py:221
Type: missing_optimization
Code: attendance_categories = TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/views.py:107
Type: missing_optimization
Code: get_geofence_id = am.Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/attendance/views.py:121
Type: missing_optimization
Code: ob.GeofenceMaster.objects.filter(id=geofence_id, enable=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_manager.py:311
Type: missing_optimization
Code: active_clients = Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:499
Type: missing_optimization
Code: active_users = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:537
Type: missing_optimization
Code: active_bus = Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:602
Type: missing_optimization
Code: 'total_jobs': Jobneed.objects.filter(enable=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:603
Type: missing_optimization
Code: 'completed_jobs': Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:606
Type: missing_optimization
Code: 'pending_jobs': Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:609
Type: missing_optimization
Code: 'active_assets': Asset.objects.filter(enable=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:610
Type: missing_optimization
Code: 'critical_assets': Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:625
Type: missing_optimization
Code: 'recent_jobs': Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:628
Type: missing_optimization
Code: 'completed_today': Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:632
Type: missing_optimization
Code: 'overdue_jobs': Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/cache_strategies.py:658
Type: missing_optimization
Code: TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:143
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:154
Type: missing_optimization
Code: aggregation = HeatmapAggregation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:200
Type: missing_optimization
Code: recent_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:338
Type: missing_optimization
Code: assignments = Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:343
Type: missing_optimization
Code: conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:381
Type: missing_optimization
Code: recent_assignments = Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:386
Type: missing_optimization
Code: recent_conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:391
Type: missing_optimization
Code: total_assignments = Assignment.objects.filter(experiment=experiment).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:392
Type: missing_optimization
Code: total_conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:535
Type: missing_optimization
Code: recent_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:539
Type: missing_optimization
Code: active_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:544
Type: missing_optimization
Code: running_experiments = Experiment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:549
Type: missing_optimization
Code: recent_assignments = Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/consumers.py:553
Type: missing_optimization
Code: recent_conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:95
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:107
Type: missing_optimization
Code: session_count = HeatmapSession.objects.filter(user=user).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:124
Type: missing_optimization
Code: similarity_count = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:134
Type: missing_optimization
Code: top_similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:193
Type: missing_optimization
Code: recent_similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:232
Type: missing_optimization
Code: old_similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:262
Type: missing_optimization
Code: high_similarity = UserSimilarity.objects.filter(similarity_score__gte=0.7).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:263
Type: missing_optimization
Code: medium_similarity = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:267
Type: missing_optimization
Code: low_similarity = UserSimilarity.objects.filter(similarity_score__lt=0.3).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/calculate_user_similarities.py:281
Type: missing_optimization
Code: high_similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/fix_compressed_emails.py:36
Type: missing_optimization
Code: suspicious_people = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:111
Type: missing_optimization
Code: recent_recs = ContentRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:133
Type: missing_optimization
Code: existing = ContentRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:174
Type: missing_optimization
Code: existing = NavigationRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:183
Type: missing_optimization
Code: NavigationRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:210
Type: missing_optimization
Code: existing = NavigationRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:218
Type: missing_optimization
Code: NavigationRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/generate_recommendations.py:257
Type: missing_optimization
Code: active_users = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/warm_caches.py:179
Type: missing_optimization
Code: active_bus = Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/warm_caches.py:217
Type: missing_optimization
Code: active_bus = Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/warm_caches.py:255
Type: missing_optimization
Code: active_users = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/management/commands/warm_caches.py:358
Type: missing_optimization
Code: TypeAssist.objects.filter(tacode=category)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/middleware/api_authentication.py:170
Type: missing_optimization
Code: api_key_obj = APIKey.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/middleware/ia_tracking.py:472
Type: missing_optimization
Code: recent_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/middleware/recommendation_middleware.py:127
Type: missing_optimization
Code: session_count = HeatmapSession.objects.filter(user=user).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/middleware/recommendation_middleware.py:268
Type: missing_optimization
Code: ContentRecommendation.objects.filter(id=rec_id).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/middleware/recommendation_middleware.py:532
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/models.py:84
Type: missing_optimization
Code: violations = cls.objects.filter(reported_at__gte=since)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/models.py:108
Type: missing_optimization
Code: deleted, _ = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/models.py:376
Type: missing_optimization
Code: deleted, _ = cls.objects.filter(timestamp__lt=cutoff).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1080
Type: missing_optimization
Code: queryset = People.objects.filter(client_id=client_id).distinct()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1482
Type: missing_optimization
Code: total_checkpoints = Jobneed.objects.filter(parent_id=tour.id).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1483
Type: missing_optimization
Code: completed_checkpoints = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1487
Type: missing_optimization
Code: missed_checkpoints = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1547
Type: missing_optimization
Code: total_checkpoints = Jobneed.objects.filter(parent_id=tour.id).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1548
Type: missing_optimization
Code: completed_checkpoints = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/queries.py:1552
Type: missing_optimization
Code: missed_checkpoints = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:77
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:103
Type: missing_optimization
Code: last_similarity_calc = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:151
Type: missing_optimization
Code: similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:169
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=similar_user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:175
Type: missing_optimization
Code: user_profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:226
Type: missing_optimization
Code: user_profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:300
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:333
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:424
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(page_url=page_url)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:506
Type: missing_optimization
Code: clicks = ClickHeatmap.objects.filter(session=session)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:534
Type: missing_optimization
Code: scrolls = ScrollHeatmap.objects.filter(session=session)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:597
Type: missing_optimization
Code: completed_experiments = Experiment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:613
Type: missing_optimization
Code: assignments = Assignment.objects.filter(variant=variant).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:614
Type: missing_optimization
Code: conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:655
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:662
Type: missing_optimization
Code: assignments = Assignment.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/recommendation_engine.py:727
Type: missing_optimization
Code: clicks = ClickHeatmap.objects.filter(session=session)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/services/geofence_service.py:60
Type: missing_optimization
Code: GeofenceMaster.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/services/geofence_service.py:190
Type: missing_optimization
Code: bus = Bt.objects.filter(client_id=client_id).values_list('id', flat=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/services/speech_to_text_service.py:144
Type: missing_optimization
Code: attachments = Attachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils.py:106
Type: missing_optimization
Code: People.objects.filter(~Q(peoplecode="NONE"), id__in=people_ids).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:277
Type: missing_optimization
Code: Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:282
Type: missing_optimization
Code: Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:287
Type: missing_optimization
Code: Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:292
Type: missing_optimization
Code: Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:297
Type: missing_optimization
Code: Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:349
Type: missing_optimization
Code: is_wp_approver = Approver.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:354
Type: missing_optimization
Code: is_sla_approver = Approver.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:390
Type: missing_optimization
Code: .objects.filter(pk__in=request.session["wizard_data"][ids])

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/business_logic.py:602
Type: missing_optimization
Code: model.objects.filter(pk__in=ids).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/file_utils.py:2757
Type: missing_optimization
Code: QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/file_utils.py:2825
Type: missing_optimization
Code: asset_codes = Asset.objects.filter(id__in=asset_ids).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/file_utils.py:2831
Type: missing_optimization
Code: bu_codes = ob.Bt.objects.filter(id__in=bu_ids).values_list("id", "bucode")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/file_utils.py:2835
Type: missing_optimization
Code: site_group_names = pm.Pgroup.objects.filter(id__in=site_group_ids).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/file_utils.py:2841
Type: missing_optimization
Code: site_type_names = ob.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/sentinel_resolvers.py:55
Type: missing_optimization
Code: none_job = Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/sentinel_resolvers.py:115
Type: missing_optimization
Code: none_asset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/utils_new/sentinel_resolvers.py:165
Type: missing_optimization
Code: none_jobneed = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/dashboard_views.py:94
Type: missing_optimization
Code: total_people = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/dashboard_views.py:100
Type: missing_optimization
Code: active_assets = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/dashboard_views.py:108
Type: missing_optimization
Code: today_attendance = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/dashboard_views.py:130
Type: missing_optimization
Code: asset_status = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/dashboard_views.py:151
Type: missing_optimization
Code: month_attendance = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:116
Type: missing_optimization
Code: clicks = ClickHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:156
Type: missing_optimization
Code: scrolls = ScrollHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:170
Type: missing_optimization
Code: max_depths = ScrollHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:193
Type: missing_optimization
Code: attention_zones = AttentionHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:238
Type: missing_optimization
Code: interactions = ElementInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:274
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:336
Type: missing_optimization
Code: velocities = ScrollHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:364
Type: missing_optimization
Code: distribution = ElementInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:405
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:413
Type: missing_optimization
Code: clicks = ClickHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:421
Type: missing_optimization
Code: scrolls = ScrollHeatmap.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:452
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:475
Type: missing_optimization
Code: auth_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:481
Type: missing_optimization
Code: anon_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:504
Type: missing_optimization
Code: clicks = ClickHeatmap.objects.filter(session__in=sessions)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:505
Type: missing_optimization
Code: interactions = ElementInteraction.objects.filter(session__in=sessions)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:536
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:617
Type: missing_optimization
Code: total_clicks = ClickHeatmap.objects.filter(session__in=sessions).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:618
Type: missing_optimization
Code: total_scrolls = ScrollHeatmap.objects.filter(session__in=sessions).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/heatmap_views.py:619
Type: missing_optimization
Code: total_interactions = ElementInteraction.objects.filter(session__in=sessions).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:93
Type: missing_optimization
Code: clicks = NavigationClick.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:143
Type: missing_optimization
Code: errors = ErrorLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:184
Type: missing_optimization
Code: pre_ia_errors = ErrorLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:189
Type: missing_optimization
Code: post_ia_errors = ErrorLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:207
Type: missing_optimization
Code: page_views = PageView.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:265
Type: missing_optimization
Code: sessions = PageView.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/monitoring_views.py:289
Type: missing_optimization
Code: avg_pages_per_session = PageView.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:115
Type: missing_optimization
Code: recent_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:119
Type: missing_optimization
Code: active_sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:123
Type: missing_optimization
Code: pages_tracked = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:128
Type: missing_optimization
Code: running_experiments = Experiment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:133
Type: missing_optimization
Code: recent_assignments = Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:137
Type: missing_optimization
Code: recent_conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:167
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:222
Type: missing_optimization
Code: recent_assignments = Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:227
Type: missing_optimization
Code: recent_conversions = Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:280
Type: missing_optimization
Code: sessions = HeatmapSession.objects.filter(page_url=page_url)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:300
Type: missing_optimization
Code: assignments = Assignment.objects.filter(experiment=experiment)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:301
Type: missing_optimization
Code: conversions = Conversion.objects.filter(assignment__experiment=experiment)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:429
Type: missing_optimization
Code: 'recent_heatmap_sessions': HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:432
Type: missing_optimization
Code: 'active_heatmap_sessions': HeatmapSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:435
Type: missing_optimization
Code: 'recent_ab_assignments': Assignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/realtime_views.py:438
Type: missing_optimization
Code: 'recent_conversions': Conversion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:54
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=request.user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:181
Type: missing_optimization
Code: content_recs = ContentRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:191
Type: missing_optimization
Code: nav_recs = NavigationRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:196
Type: missing_optimization
Code: profile = UserBehaviorProfile.objects.filter(user=request.user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:201
Type: missing_optimization
Code: similarities = UserSimilarity.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:224
Type: missing_optimization
Code: content_recs = ContentRecommendation.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:262
Type: missing_optimization
Code: existing_feedback = RecommendationFeedback.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/views/recommendation_views.py:336
Type: missing_optimization
Code: ContentRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/widgets.py:183
Type: missing_optimization
Code: client = om.Bt.objects.filter(bucode=client_code).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/widgets.py:188
Type: missing_optimization
Code: return self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/core/widgets.py:213
Type: missing_optimization
Code: client = om.Bt.objects.filter(bucode=client_code).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/ai_enhanced_engine.py:1220
Type: missing_optimization
Code: lambda: FaceRecognitionModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/ai_enhanced_engine.py:1222
Type: missing_optimization
Code: ).first() or FaceRecognitionModel.objects.filter(status='ACTIVE').first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/analytics.py:67
Type: missing_optimization
Code: base_queryset = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/analytics.py:217
Type: missing_optimization
Code: anomalies = AnomalyDetectionResult.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/analytics.py:272
Type: missing_optimization
Code: profiles = UserBehaviorProfile.objects.filter(user_id__in=user_ids)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/analytics.py:326
Type: missing_optimization
Code: verification_logs = FaceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/analytics.py:542
Type: missing_optimization
Code: recent_logs = FaceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/enhanced_engine.py:45
Type: missing_optimization
Code: system_configs = FaceRecognitionConfig.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/enhanced_engine.py:830
Type: missing_optimization
Code: recent_fraudulent = FaceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/enhanced_engine.py:933
Type: missing_optimization
Code: primary_model = FaceRecognitionModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/enhanced_engine.py:939
Type: missing_optimization
Code: primary_model = FaceRecognitionModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/integrations.py:319
Type: missing_optimization
Code: recent_attendance = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/calibrate_thresholds.py:154
Type: missing_optimization
Code: face_model = FaceRecognitionModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:95
Type: missing_optimization
Code: FaceRecognitionConfig.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:99
Type: missing_optimization
Code: AnomalyDetectionConfig.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:561
Type: missing_optimization
Code: face_models = FaceRecognitionModel.objects.filter(status='ACTIVE')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:570
Type: missing_optimization
Code: spoof_models = AntiSpoofingModel.objects.filter(is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:579
Type: missing_optimization
Code: anomaly_models = AnomalyDetectionModel.objects.filter(is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:588
Type: missing_optimization
Code: behavioral_models = BehavioralModel.objects.filter(is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:597
Type: missing_optimization
Code: face_configs = FaceRecognitionConfig.objects.filter(is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:598
Type: missing_optimization
Code: anomaly_configs = AnomalyDetectionConfig.objects.filter(is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:645
Type: missing_optimization
Code: recent_attendance = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:649
Type: missing_optimization
Code: face_recognition_attendance = PeopleEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/management/commands/init_ai_systems.py:655
Type: missing_optimization
Code: active_users = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/services.py:255
Type: missing_optimization
Code: face_model = FaceRecognitionModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/signals.py:62
Type: missing_optimization
Code: existing_primary = FaceEmbedding.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/signals.py:91
Type: missing_optimization
Code: next_embedding = FaceEmbedding.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/signals.py:233
Type: missing_optimization
Code: recent_logs = FaceVerificationLog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/face_recognition/signals.py:262
Type: missing_optimization
Code: other_primary = FaceEmbedding.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/models.py:277
Type: missing_optimization
Code: queryset = cls.objects.filter(created_at__gte=since_date)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/models.py:314
Type: missing_optimization
Code: previous_count = cls.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/models.py:616
Type: missing_optimization
Code: fix_actions = FixAction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:655
Type: missing_optimization
Code: 'active_signatures': AnomalySignature.objects.filter(status='active').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:656
Type: missing_optimization
Code: 'critical_anomalies': AnomalySignature.objects.filter(severity='critical').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:658
Type: missing_optimization
Code: 'occurrences_24h': AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:661
Type: missing_optimization
Code: 'occurrences_7d': AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:665
Type: missing_optimization
Code: 'unresolved_occurrences': AnomalyOccurrence.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/anomaly_detector.py:675
Type: missing_optimization
Code: 'recurring_issues': AnomalySignature.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/fix_suggester.py:470
Type: missing_optimization
Code: 'auto_applicable_count': FixSuggestion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/issue_tracker/services/fix_suggester.py:473
Type: missing_optimization
Code: 'high_confidence_count': FixSuggestion.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/graphql_schema.py:350
Type: missing_optimization
Code: queryset = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/graphql_schema.py:416
Type: missing_optimization
Code: queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/graphql_schema.py:450
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/graphql_schema.py:467
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/graphql_schema.py:548
Type: missing_optimization
Code: journal_entries = list(JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:298
Type: missing_optimization
Code: old_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:318
Type: missing_optimization
Code: old_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:372
Type: missing_optimization
Code: orphaned_media = JournalMediaAttachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:386
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:392
Type: missing_optimization
Code: problematic_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:408
Type: missing_optimization
Code: users_with_auto_delete = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:418
Type: missing_optimization
Code: user_overdue = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:437
Type: missing_optimization
Code: invalid_user_refs = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:443
Type: missing_optimization
Code: invalid_content_refs = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:504
Type: missing_optimization
Code: if not User.objects.filter(id=user_id, tenant=tenant).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:558
Type: missing_optimization
Code: journal_entries = JournalEntry.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:559
Type: missing_optimization
Code: wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:562
Type: missing_optimization
Code: media_attachments = JournalMediaAttachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/migrate_journal_data.py:676
Type: missing_optimization
Code: users_with_data = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:179
Type: missing_optimization
Code: 'users_configured': User.objects.filter(tenant=tenant).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:192
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:233
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:503
Type: missing_optimization
Code: system_user = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:510
Type: missing_optimization
Code: system_user = User.objects.filter(tenant=tenant).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:524
Type: missing_optimization
Code: journal_permissions = Permission.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:529
Type: missing_optimization
Code: wellness_groups = Group.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:537
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:557
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:558
Type: missing_optimization
Code: users_with_privacy = JournalPrivacySettings.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:580
Type: missing_optimization
Code: tenant_content = WellnessContent.objects.filter(tenant=tenant, is_active=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:685
Type: missing_optimization
Code: test_user = User.objects.filter(tenant=tenant).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:697
Type: missing_optimization
Code: journal_count = JournalEntry.objects.filter(user__tenant=tenant).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/management/commands/setup_journal_wellness_system.py:698
Type: missing_optimization
Code: content_count = WellnessContent.objects.filter(tenant=tenant).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/models.py:511
Type: missing_optimization
Code: JournalMediaAttachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/mqtt_integration.py:556
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/mqtt_integration.py:557
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/mqtt_integration.py:563
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/permissions.py:213
Type: missing_optimization
Code: permissions = Permission.objects.filter(codename__in=permission_codenames)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/permissions.py:225
Type: missing_optimization
Code: journal_wellness_groups = Group.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/permissions.py:695
Type: missing_optimization
Code: tenant_users = User.objects.filter(tenant=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:192
Type: missing_optimization
Code: users_to_process = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:300
Type: missing_optimization
Code: journal_entries = JournalEntry.objects.filter(user=user, is_deleted=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:304
Type: missing_optimization
Code: wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:384
Type: missing_optimization
Code: journal_entries = JournalEntry.objects.filter(user=user).order_by('timestamp')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:388
Type: missing_optimization
Code: wellness_interactions = WellnessContentInteraction.objects.filter(user=user).order_by('interaction_date')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:487
Type: missing_optimization
Code: journal_entries = JournalEntry.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:511
Type: missing_optimization
Code: wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:525
Type: missing_optimization
Code: media_attachments = JournalMediaAttachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:641
Type: missing_optimization
Code: old_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:665
Type: missing_optimization
Code: shared_wellbeing_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:678
Type: missing_optimization
Code: manager_accessible_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:688
Type: missing_optimization
Code: users_with_retention = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:701
Type: missing_optimization
Code: overdue_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/privacy.py:718
Type: missing_optimization
Code: problematic_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/search.py:640
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/search.py:701
Type: missing_optimization
Code: queryset = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/search.py:759
Type: missing_optimization
Code: entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/search.py:831
Type: missing_optimization
Code: user_entries = JournalEntry.objects.filter(user=user, is_deleted=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:386
Type: missing_optimization
Code: changed_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:393
Type: missing_optimization
Code: deleted_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:467
Type: missing_optimization
Code: existing_media = JournalMediaAttachment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:828
Type: missing_optimization
Code: pending_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:893
Type: missing_optimization
Code: pending_count = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:898
Type: missing_optimization
Code: error_count = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/sync.py:903
Type: missing_optimization
Code: last_successful_sync = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/views.py:358
Type: missing_optimization
Code: queryset = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/views.py:571
Type: missing_optimization
Code: existing_entry = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/journal/views.py:599
Type: missing_optimization
Code: server_changes = list(JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/code_quality.py:154
Type: missing_optimization
Code: model_symbols = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/code_quality.py:196
Type: missing_optimization
Code: has_str_method = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/impact_analyzer.py:272
Type: missing_optimization
Code: django_urls = DjangoURL.objects.filter(view_name__icontains=view_name)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/impact_analyzer.py:307
Type: missing_optimization
Code: models_in_file = DjangoModel.objects.filter(file__path=file_path)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/impact_analyzer.py:387
Type: missing_optimization
Code: urls_in_file = DjangoURL.objects.filter(file__path=file_path)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/impact_analyzer.py:438
Type: missing_optimization
Code: return TestCoverage.objects.filter(file=file_obj).exists()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/analyzers/impact_analyzer.py:471
Type: missing_optimization
Code: indexed_files = IndexedFile.objects.filter(path__in=affected_files).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/generators/doc_generator.py:64
Type: missing_optimization
Code: urls = DjangoURL.objects.filter(route__startswith='/api/')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/generators/doc_generator.py:77
Type: missing_optimization
Code: graphql_queries = GraphQLDefinition.objects.filter(kind='query')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/generators/migration_generator.py:165
Type: missing_optimization
Code: db_models = DjangoModel.objects.filter(app_label=app_label)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/indexers/incremental_indexer.py:417
Type: missing_optimization
Code: IndexedFile.objects.filter(path=file_path).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/indexers/python_indexer.py:263
Type: missing_optimization
Code: CodeSymbol.objects.filter(file=self.file_obj).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/indexers/python_indexer.py:264
Type: missing_optimization
Code: SymbolRelation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:76
Type: missing_optimization
Code: symbols = CodeSymbol.objects.filter(file=indexed_file).order_by('span_start')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:106
Type: missing_optimization
Code: urls = DjangoURL.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:148
Type: missing_optimization
Code: models = DjangoModel.objects.filter(model_name__icontains=model_name)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:181
Type: missing_optimization
Code: graphql_defs = GraphQLDefinition.objects.filter(name__icontains=type_name)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:219
Type: missing_optimization
Code: symbols = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:229
Type: missing_optimization
Code: files = IndexedFile.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:243
Type: missing_optimization
Code: urls = DjangoURL.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:258
Type: missing_optimization
Code: models = DjangoModel.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:272
Type: missing_optimization
Code: graphql_defs = GraphQLDefinition.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:299
Type: missing_optimization
Code: return CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:306
Type: missing_optimization
Code: return CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:312
Type: missing_optimization
Code: symbols = CodeSymbol.objects.filter(name=symbol_ref)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:445
Type: missing_optimization
Code: symbols_in_file = CodeSymbol.objects.filter(file=file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:469
Type: missing_optimization
Code: import_symbols = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:478
Type: missing_optimization
Code: tests = TestCase.objects.filter(file=file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:491
Type: missing_optimization
Code: models = DjangoModel.objects.filter(file=file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:502
Type: missing_optimization
Code: urls = DjangoURL.objects.filter(file=file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:513
Type: missing_optimization
Code: graphql_defs = GraphQLDefinition.objects.filter(file=file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:526
Type: missing_optimization
Code: symbol = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:562
Type: missing_optimization
Code: related = DjangoURL.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:574
Type: missing_optimization
Code: return CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_explain.py:597
Type: missing_optimization
Code: model_refs = CodeSymbol.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_index.py:245
Type: missing_optimization
Code: existing = IndexedFile.objects.filter(path=rel_path, sha=file_sha).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_index.py:291
Type: missing_optimization
Code: CodeSymbol.objects.filter(file=file_obj).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:75
Type: missing_optimization
Code: symbol = CodeSymbol.objects.filter(name=symbol_name).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:86
Type: missing_optimization
Code: flaky_tests = TestCase.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:94
Type: missing_optimization
Code: slow_tests = TestCase.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:110
Type: missing_optimization
Code: coverage_records = TestCoverage.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:137
Type: missing_optimization
Code: test_cases = TestCase.objects.filter(file__path=pattern)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:151
Type: missing_optimization
Code: file_symbols = CodeSymbol.objects.filter(file=indexed_file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:156
Type: missing_optimization
Code: related_relations = SymbolRelation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/management/commands/mentor_test.py:174
Type: missing_optimization
Code: coverage_records = TestCoverage.objects.filter(file=symbol.file)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/monitoring/dashboard.py:193
Type: missing_optimization
Code: complex_symbols = CodeSymbol.objects.filter(complexity__gt=10).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/monitoring/dashboard.py:281
Type: missing_optimization
Code: complex_symbols = CodeSymbol.objects.filter(complexity__gt=10).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/monitoring/dashboard.py:282
Type: missing_optimization
Code: very_complex_symbols = CodeSymbol.objects.filter(complexity__gt=20).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/tests/base.py:124
Type: missing_optimization
Code: file_obj = IndexedFile.objects.filter(path=path).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/mentor/tests/base.py:145
Type: missing_optimization
Code: relation = SymbolRelation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:297
Type: missing_optimization
Code: pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:391
Type: missing_optimization
Code: parent_bu = om.Bt.objects.filter(bucode=row['Belongs To*']).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:590
Type: missing_optimization
Code: if not om.TypeAssist.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:751
Type: missing_optimization
Code: if not om.Bt.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:885
Type: missing_optimization
Code: get_geofence = om.Bt.objects.filter(bucode=row["Site*"]).values("gpslocation")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:1027
Type: missing_optimization
Code: get_people = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:1033
Type: missing_optimization
Code: get_geofence_name = om.GeofenceMaster.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/admin.py:1255
Type: missing_optimization
Code: if om.Shift.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:90
Type: missing_optimization
Code: self.fields["tatype"].queryset = obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:138
Type: missing_optimization
Code: queryset=obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:257
Type: missing_optimization
Code: self.fields["identifier"].queryset = obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:260
Type: missing_optimization
Code: self.fields["butype"].queryset = obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:264
Type: missing_optimization
Code: self.fields["parent"].queryset = obm.Bt.objects.filter(id__in=qset)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:271
Type: missing_optimization
Code: self.fields["siteincharge"].queryset = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:275
Type: missing_optimization
Code: self.fields["designation"].queryset = obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:305
Type: missing_optimization
Code: existing = obm.Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:459
Type: missing_optimization
Code: self.fields["designation"].queryset = obm.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/forms.py:534
Type: missing_optimization
Code: self.fields["bu"].queryset = obm.Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/management/commands/init_intelliwiz.py:163
Type: missing_optimization
Code: if not force and TypeAssist.objects.filter(tacode='PEOPLETYPE').exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:23
Type: missing_optimization
Code: qset := pm.Pgbelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:275
Type: missing_optimization
Code: if pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:283
Type: missing_optimization
Code: if pm.People.objects.filter(loginid=R["loginid"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:286
Type: missing_optimization
Code: if pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:296
Type: missing_optimization
Code: updated = pm.People.objects.filter(pk=R["pk"]).update(**PostData)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:300
Type: missing_optimization
Code: pm.People.objects.filter(pk=R["pk"]).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:303
Type: missing_optimization
Code: qset = pm.People.objects.filter(id=ID).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:350
Type: missing_optimization
Code: pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:463
Type: missing_optimization
Code: TypeAssist.objects.filter(id=int(key)).values("tacode").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/managers.py:665
Type: missing_optimization
Code: qset = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/models_original_backup.py:1544
Type: missing_optimization
Code: dependent_count = AIChangeRecord.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/models_original_backup.py:1765
Type: missing_optimization
Code: eligible_approvers = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/utils.py:66
Type: missing_optimization
Code: return TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/utils.py:76
Type: missing_optimization
Code: childs = Bt.objects.filter(id__in=childs).order_by("id")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/utils.py:327
Type: missing_optimization
Code: is_exists = People.objects.filter(peoplecode=peoplecode).exists()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/utils.py:481
Type: missing_optimization
Code: p.peoplecode: p for p in People.objects.filter(peoplecode__in=peoplecodes)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/views.py:284
Type: missing_optimization
Code: sites = Bt.objects.filter(id__in=data).values("id", "bucode", "buname")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/views.py:296
Type: missing_optimization
Code: sites = Bt.objects.filter(id=req_buid).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/views.py:329
Type: missing_optimization
Code: Pgbelonging.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:361
Type: missing_optimization
Code: tenant_users = People.objects.filter(client=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:380
Type: missing_optimization
Code: tenant_users = People.objects.filter(client=tenant)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:407
Type: missing_optimization
Code: 'enabled_users': People.objects.filter(capabilities__has_key='can_use_conversational_onboarding').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:408
Type: missing_optimization
Code: 'approvers': People.objects.filter(capabilities__has_key='can_approve_ai_recommendations').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin.py:409
Type: missing_optimization
Code: 'kb_managers': People.objects.filter(capabilities__has_key='can_manage_knowledge_base').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:143
Type: missing_optimization
Code: return ExperimentAssignment.objects.filter(experiment=obj).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:354
Type: missing_optimization
Code: active_users = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_personalization.py:418
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:44
Type: missing_optimization
Code: recent_knowledge = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:51
Type: missing_optimization
Code: 'chunks_with_vectors': AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:54
Type: missing_optimization
Code: 'stale_chunks': AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:62
Type: missing_optimization
Code: count = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:108
Type: missing_optimization
Code: chunks = AuthoritativeKnowledgeChunk.objects.filter(knowledge=doc)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:239
Type: missing_optimization
Code: recent_sessions = ConversationSession.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:240
Type: missing_optimization
Code: recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:305
Type: missing_optimization
Code: chunk_count = AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:342
Type: missing_optimization
Code: stale_docs = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:354
Type: missing_optimization
Code: AuthoritativeKnowledgeChunk.objects.filter(knowledge=doc).update(is_current=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:386
Type: missing_optimization
Code: sessions = ConversationSession.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:387
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:679
Type: missing_optimization
Code: total_clients = Bt.objects.filter(enable=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:685
Type: missing_optimization
Code: clients_completed = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:690
Type: missing_optimization
Code: clients_using_templates = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:753
Type: missing_optimization
Code: sessions_24h = ConversationSession.objects.filter(cdtz__gte=last_24h)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:754
Type: missing_optimization
Code: recommendations_24h = LLMRecommendation.objects.filter(cdtz__gte=last_24h)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:809
Type: missing_optimization
Code: total_sessions = ConversationSession.objects.filter(cdtz__gte=last_30_days).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:811
Type: missing_optimization
Code: template_usage = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:816
Type: missing_optimization
Code: ai_approvals = AIChangeSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/admin_views.py:822
Type: missing_optimization
Code: knowledge_validations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:74
Type: missing_optimization
Code: existing_bu = Bt.objects.filter(bucode=bu_code, parent=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:85
Type: missing_optimization
Code: existing_shift = Shift.objects.filter(shiftname=shift_name, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:96
Type: missing_optimization
Code: existing_ta = TypeAssist.objects.filter(tacode=ta_code, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:115
Type: missing_optimization
Code: existing_obj = model_class.objects.filter(**lookup_filter).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:492
Type: missing_optimization
Code: existing_shift = Shift.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/integration/mapper.py:602
Type: missing_optimization
Code: existing_ta = TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:424
Type: missing_optimization
Code: approved_review = KnowledgeReview.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/knowledge_views.py:836
Type: missing_optimization
Code: docs = AuthoritativeKnowledge.objects.filter(is_current=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:312
Type: missing_optimization
Code: recent_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:325
Type: missing_optimization
Code: stuck_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:376
Type: missing_optimization
Code: recent_changesets = AIChangeSet.objects.filter(cdtz__gte=cutoff_time)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:524
Type: missing_optimization
Code: total_conversations = ConversationSession.objects.filter(cdtz__gte=cutoff_time).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:525
Type: missing_optimization
Code: completed_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:531
Type: missing_optimization
Code: total_recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff_time).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:532
Type: missing_optimization
Code: approved_recommendations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:538
Type: missing_optimization
Code: total_changesets = AIChangeSet.objects.filter(cdtz__gte=cutoff_time).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:539
Type: missing_optimization
Code: successful_changesets = AIChangeSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:577
Type: missing_optimization
Code: stuck_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:592
Type: missing_optimization
Code: recent_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:597
Type: missing_optimization
Code: error_conversations = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring.py:614
Type: missing_optimization
Code: failed_changesets = AIChangeSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring_views.py:227
Type: missing_optimization
Code: recent_conversations = ConversationSession.objects.filter(cdtz__gte=cutoff_time).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/monitoring_views.py:228
Type: missing_optimization
Code: recent_recommendations = LLMRecommendation.objects.filter(cdtz__gte=cutoff_time).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/personalization_views.py:73
Type: missing_optimization
Code: profile = PreferenceProfile.objects.filter(user=user, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/personalization_views.py:76
Type: missing_optimization
Code: profile = PreferenceProfile.objects.filter(user__isnull=True, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/personalization_views.py:127
Type: missing_optimization
Code: profile = PreferenceProfile.objects.filter(user=user).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/personalization_views.py:300
Type: missing_optimization
Code: assignments = ExperimentAssignment.objects.filter(experiment=experiment)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/personalization_views.py:687
Type: missing_optimization
Code: assignments = ExperimentAssignment.objects.filter(experiment=experiment)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:42
Type: missing_optimization
Code: pending_docs = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:135
Type: missing_optimization
Code: AuthoritativeKnowledgeChunk.objects.filter(knowledge=document).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:196
Type: missing_optimization
Code: pending_jobs = KnowledgeIngestionJob.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:318
Type: missing_optimization
Code: chunks_created = AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:322
Type: missing_optimization
Code: embeddings_generated = AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:363
Type: missing_optimization
Code: failed_jobs = KnowledgeIngestionJob.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:461
Type: missing_optimization
Code: docs_without_embeddings = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:480
Type: missing_optimization
Code: completed_jobs = KnowledgeIngestionJob.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:629
Type: missing_optimization
Code: documents = AuthoritativeKnowledge.objects.filter(is_current=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:631
Type: missing_optimization
Code: documents = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/background_embedding_jobs.py:676
Type: missing_optimization
Code: recent_jobs = KnowledgeIngestionJob.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:112
Type: missing_optimization
Code: sessions_query = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:373
Type: missing_optimization
Code: sessions_query = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:443
Type: missing_optimization
Code: sessions_query = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:720
Type: missing_optimization
Code: first_time_sessions = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:753
Type: missing_optimization
Code: all_sessions = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:764
Type: missing_optimization
Code: previous_sessions = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/funnel_analytics.py:787
Type: missing_optimization
Code: admin_sessions = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:78
Type: missing_optimization
Code: knowledge_items = self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:129
Type: missing_optimization
Code: with_vectors = self.model.objects.filter(content_vector__isnull=False).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:130
Type: missing_optimization
Code: current_knowledge = self.model.objects.filter(is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:198
Type: missing_optimization
Code: knowledge_items = self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:225
Type: missing_optimization
Code: sources = self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:282
Type: missing_optimization
Code: count = self.model.objects.filter(authority_level=level, is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:285
Type: missing_optimization
Code: recent_additions = self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:293
Type: missing_optimization
Code: 'oldest_knowledge': self.model.objects.filter(is_current=True).order_by('publication_date').first(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:294
Type: missing_optimization
Code: 'newest_knowledge': self.model.objects.filter(is_current=True).order_by('-publication_date').first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:407
Type: missing_optimization
Code: self.chunk_model.objects.filter(knowledge=knowledge).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:513
Type: missing_optimization
Code: deleted_count = self.chunk_model.objects.filter(knowledge=knowledge).delete()[0]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:524
Type: missing_optimization
Code: chunks_with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:525
Type: missing_optimization
Code: current_chunks = self.chunk_model.objects.filter(is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:664
Type: missing_optimization
Code: chunk_count = self.chunk_model.objects.filter(knowledge=knowledge).update(content_vector=None)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:680
Type: missing_optimization
Code: docs_with_vectors = self.knowledge_model.objects.filter(content_vector__isnull=False).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:683
Type: missing_optimization
Code: chunks_with_vectors = self.chunk_model.objects.filter(content_vector__isnull=False).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:684
Type: missing_optimization
Code: current_chunks = self.chunk_model.objects.filter(is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:689
Type: missing_optimization
Code: count = self.chunk_model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge.py:2664
Type: missing_optimization
Code: sample_chunks = self.chunk_model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/learning.py:802
Type: missing_optimization
Code: recent_rec = LLMRecommendation.objects.filter(session=session).order_by('-cdtz').first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/learning.py:868
Type: missing_optimization
Code: profile = PreferenceProfile.objects.filter(user=user, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/learning.py:872
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:296
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:318
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:340
Type: missing_optimization
Code: total_sessions = ConversationSession.objects.filter(cdtz__gte=since).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:344
Type: missing_optimization
Code: error_sessions = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:485
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:496
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:507
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:518
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:531
Type: missing_optimization
Code: assignments = ExperimentAssignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:539
Type: missing_optimization
Code: error_interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:614
Type: missing_optimization
Code: interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:694
Type: missing_optimization
Code: assignments = ExperimentAssignment.objects.filter(experiment=experiment)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/monitoring.py:726
Type: missing_optimization
Code: user_interactions = RecommendationInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:120
Type: missing_optimization
Code: recommendations_query = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:163
Type: missing_optimization
Code: recommendations_query = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:385
Type: missing_optimization
Code: recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:519
Type: missing_optimization
Code: recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:546
Type: missing_optimization
Code: recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:684
Type: missing_optimization
Code: stale_count = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:752
Type: missing_optimization
Code: total_docs = AuthoritativeKnowledge.objects.filter(is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:753
Type: missing_optimization
Code: total_chunks = AuthoritativeKnowledgeChunk.objects.filter(is_current=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:754
Type: missing_optimization
Code: docs_with_vectors = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:758
Type: missing_optimization
Code: chunks_with_vectors = AuthoritativeKnowledgeChunk.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:765
Type: missing_optimization
Code: stale_docs = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:771
Type: missing_optimization
Code: recent_jobs = KnowledgeIngestionJob.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:780
Type: missing_optimization
Code: count = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/observability.py:827
Type: missing_optimization
Code: jobs = KnowledgeIngestionJob.objects.filter(cdtz__gte=cutoff)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/optimization.py:269
Type: missing_optimization
Code: profile = PreferenceProfile.objects.filter(user=user, client=client).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/personalization.py:43
Type: missing_optimization
Code: self.preference_profile = PreferenceProfile.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/personalization.py:791
Type: missing_optimization
Code: existing_assignment = ExperimentAssignment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/personalized_llm.py:221
Type: missing_optimization
Code: active_experiments = Experiment.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/security.py:460
Type: missing_optimization
Code: existing_docs = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/security.py:547
Type: missing_optimization
Code: similar_candidates = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/security.py:791
Type: missing_optimization
Code: exact_matches = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/security.py:877
Type: missing_optimization
Code: older_versions = AuthoritativeKnowledge.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/concurrency.py:70
Type: missing_optimization
Code: existing = ConversationSession.objects.filter(...)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/preflight.py:211
Type: missing_optimization
Code: client_groups = Pgroup.objects.filter(client=self.client).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/preflight.py:219
Type: missing_optimization
Code: group_exists = Pgroup.objects.filter(client=self.client, pgname__icontains=group_name).exists()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/preflight.py:227
Type: missing_optimization
Code: user_group_count = Pgbelonging.objects.filter(user=self.user).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/preflight.py:260
Type: missing_optimization
Code: exists = TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/utils/preflight.py:275
Type: missing_optimization
Code: total_typeassist = TypeAssist.objects.filter(client=self.client, is_active=True).count()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views.py:79
Type: missing_optimization
Code: existing_session = ConversationSession.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views.py:297
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views_phase2.py:251
Type: missing_optimization
Code: latest_rec = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views_phase2.py:490
Type: missing_optimization
Code: latest_rec = LLMRecommendation.objects.filter(session=session).order_by('-cdtz').first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views_phase2.py:634
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(session=session).order_by('cdtz')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/views_ui_compat.py:227
Type: missing_optimization
Code: recommendations = LLMRecommendation.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:573
Type: missing_optimization
Code: return Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:665
Type: missing_optimization
Code: if not Pgroup.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:745
Type: missing_optimization
Code: if not pm.Pgbelonging.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/admin.py:1022
Type: missing_optimization
Code: if not pm.People.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:270
Type: missing_optimization
Code: self.fields["peopletype"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:276
Type: missing_optimization
Code: self.fields["department"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:279
Type: missing_optimization
Code: self.fields["designation"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:285
Type: missing_optimization
Code: self.fields["bu"].queryset = om.Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:288
Type: missing_optimization
Code: self.fields["location"].queryset = Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:410
Type: missing_optimization
Code: self.fields["grouplead"].queryset = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:460
Type: missing_optimization
Code: queryset=pm.Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:630
Type: missing_optimization
Code: self.fields["tempincludes"].choices = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:674
Type: missing_optimization
Code: client = om.Bt.objects.filter(id=self.request.session["client_id"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/forms.py:677
Type: missing_optimization
Code: current_ppl_count = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/management/commands/init_youtility.py:63
Type: missing_optimization
Code: #         if TypeAssist.objects.filter(tacode='PEOPLETYPE').exists(): return

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/management/commands/setup_ai_capabilities.py:82
Type: missing_optimization
Code: users_to_update = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:148
Type: missing_optimization
Code: Bt.objects.filter(id__gte=12, id__lte=150)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:210
Type: missing_optimization
Code: Pgbelonging.objects.filter(assignsites_id=bu_id).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:216
Type: missing_optimization
Code: DeviceEventlog.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:320
Type: missing_optimization
Code: if Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:508
Type: missing_optimization
Code: qset = Bt.objects.filter(id__in=ids).annotate(bu_id=F("id")).values(*fields)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:518
Type: missing_optimization
Code: people = People.objects.filter(id=peopleid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/managers.py:529
Type: missing_optimization
Code: People.objects.filter(id=peopleid)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/services.py:11
Type: missing_optimization
Code: user = pm.People.objects.filter(loginid=username).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/services/authentication_service.py:192
Type: missing_optimization
Code: user_query = People.objects.filter(loginid=loginid).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:150
Type: missing_optimization
Code: user = People.objects.filter(email__exact=val)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:163
Type: missing_optimization
Code: user = People.objects.filter(mobno__exact=val)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:229
Type: missing_optimization
Code: web = Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:236
Type: missing_optimization
Code: mob = Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:243
Type: missing_optimization
Code: portlet = Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:250
Type: missing_optimization
Code: report = Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:257
Type: missing_optimization
Code: noc = Capability.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:431
Type: missing_optimization
Code: return pm.People.objects.filter(bu__btid=site.btid).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/utils.py:475
Type: missing_optimization
Code: users_with_email = People.objects.filter(email=user.email)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:94
Type: missing_optimization
Code: user = pm.People.objects.filter(loginid=loginid).values('people_extras__userfor')

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:677
Type: missing_optimization
Code: peoples = pm.Pgbelonging.objects.filter(pgroup=obj).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:693
Type: missing_optimization
Code: pm.Pgbelonging.objects.filter(pgroup_id=int(pk)).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:846
Type: missing_optimization
Code: pm.Pgbelonging.objects.filter(pgroup_id=obj.id).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:853
Type: missing_optimization
Code: sites = pm.Pgbelonging.objects.filter(pgroup=obj).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:976
Type: missing_optimization
Code: pm.Pgbelonging.objects.filter(pgroup_id=pg.id).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/views.py:1005
Type: missing_optimization
Code: pm.People.objects.filter(id=request.user.id).update(bu_id=bu_id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:53
Type: missing_optimization
Code: self.fields["site_type_includes"].choices = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:64
Type: missing_optimization
Code: self.fields["site_grp_includes"].choices = pm.Pgroup.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:357
Type: missing_optimization
Code: pm.Pgroup.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:402
Type: missing_optimization
Code: self.fields["cc"].choices = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:405
Type: missing_optimization
Code: self.fields["to_addr"].choices = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:521
Type: missing_optimization
Code: self.fields["cc"].choices = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/forms.py:524
Type: missing_optimization
Code: self.fields["to_addr"].choices = pm.People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/assetwise_task_status.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/dynamic_detailed_tour_summary.py:89
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/dynamic_tour_details.py:56
Type: missing_optimization
Code: parents = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/dynamic_tour_details.py:206
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/dynamic_tour_list.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/list_of_task.py:89
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/list_of_tickets.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/list_of_tours.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/log_sheet.py:99
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/ppm_summary.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/service_level_agreement.py:68
Type: missing_optimization
Code: wom_details = Wom.objects.filter(id=self.formdata.get("id")).values_list(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/service_level_agreement.py:91
Type: missing_optimization
Code: wom = Wom.objects.filter(parent_id=self.formdata.get("id")).order_by("-id")[1]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/service_level_agreement.py:92
Type: missing_optimization
Code: wom_details = WomDetails.objects.filter(wom_id=wom.id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/site_visit_report.py:80
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/sitereport.py:125
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/static_detailed_tour_summary.py:89
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/static_tour_details.py:55
Type: missing_optimization
Code: parents = Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/static_tour_details.py:207
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/static_tour_list.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/task_summary.py:114
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/tour_summary.py:89
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/work_order_list.py:86
Type: missing_optimization
Code: bt = Bt.objects.filter(id=self.client_id).values("id", "buname").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/workpermit.py:83
Type: missing_optimization
Code: obj = Wom.objects.filter(id=id).values("other_data").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/report_designs/workpermit.py:91
Type: missing_optimization
Code: obj = Wom.objects.filter(id=id).values("other_data").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:107
Type: missing_optimization
Code: objects = QuestionSet.objects.filter(type="SITEREPORT").values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:259
Type: missing_optimization
Code: qset = self.model.objects.filter(parent_id=parent).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:278
Type: missing_optimization
Code: objs = self.model.objects.filter(parent_id=int(R["parent"])).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:367
Type: missing_optimization
Code: P["model"].objects.filter(id=R["id"]).update(enable=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:455
Type: missing_optimization
Code: P["model"].objects.filter(id=R["id"]).update(enable=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:543
Type: missing_optimization
Code: P["model"].objects.filter(id=R["id"]).update(enable=False)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:605
Type: missing_optimization
Code: on.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:617
Type: missing_optimization
Code: Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:627
Type: missing_optimization
Code: QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/reports/views.py:884
Type: missing_optimization
Code: data = self.P["model"].objects.filter(bu_id=S["bu_id"]).values().iterator()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:359
Type: missing_optimization
Code: if not om.Bt.objects.filter(bucode=client_code, identifier='CLIENT').exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:365
Type: missing_optimization
Code: if not om.Bt.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:423
Type: missing_optimization
Code: if Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:644
Type: missing_optimization
Code: if Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:931
Type: missing_optimization
Code: if not Job.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/admin.py:1120
Type: missing_optimization
Code: if not Job.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:251
Type: missing_optimization
Code: self.fields["asset"].queryset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:363
Type: missing_optimization
Code: self.fields["asset"].queryset = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:366
Type: missing_optimization
Code: self.fields["qset"].queryset = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:434
Type: missing_optimization
Code: self.fields["sgroup"].queryset = pm.Pgroup.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:443
Type: missing_optimization
Code: self.fields["shift"].queryset = ob.Shift.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/forms.py:682
Type: missing_optimization
Code: self.fields["ticketcategory"].queryset = ob.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/services/scheduling_service.py:506
Type: missing_optimization
Code: overlapping_jobs = Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/services/scheduling_service.py:541
Type: missing_optimization
Code: checkpoints = Job.objects.filter(parent_id=tour_id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:19
Type: missing_optimization
Code: is_job_modified = am.Job.objects.filter(id__in = jobids, mdtz__gt = F('cdtz')).first() # the job is modified

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:20
Type: missing_optimization
Code: dynamic_jobneed_exist = am.Jobneed.objects.filter(parent_id=1,jobstatus='ASSIGNED',job_id__in = jobids).exists() #dynamic job exist

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:26
Type: missing_optimization
Code: jobs = am.Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:70
Type: missing_optimization
Code: jobs = am.Job.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:234
Type: missing_optimization
Code: jn = am.Jobneed.objects.filter(id = jn.id).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:565
Type: missing_optimization
Code: job_ids = am.Job.objects.filter(parent_id=job_id).values_list('id', flat=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:572
Type: missing_optimization
Code: jobneed_ids = am.Jobneed.objects.filter(plandatetime__gt=dtimezone.now(), job_id__in=job_ids).values_list('id', flat=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:573
Type: missing_optimization
Code: jnd_count = am.JobneedDetails.objects.filter(jobneed_id__in=jobneed_ids).update(cdtz=old_date, mdtz=old_date)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:576
Type: missing_optimization
Code: jn_count = am.Jobneed.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:581
Type: missing_optimization
Code: am.Job.objects.filter(id=job_id).update(cdtz=F('mdtz'))

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:589
Type: missing_optimization
Code: Reminder.objects.filter(reminderdate__gt = datetime.now(timezone.utc), job_id = jobid).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/utils.py:817
Type: missing_optimization
Code: if rec := am.Job.objects.filter(id = job['id']).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:1042
Type: missing_optimization
Code: Job.objects.filter(parent_id=job["id"]).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:1920
Type: missing_optimization
Code: obj = P["model"].objects.filter(id=R["id"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2364
Type: missing_optimization
Code: updated = Job.objects.filter(parent_id=pk).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2375
Type: missing_optimization
Code: #         job = Job.objects.filter(id = job.id).values()[0]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2376
Type: missing_optimization
Code: #         self.params['model'].objects.filter(parent_id = job['id']).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2484
Type: missing_optimization
Code: job = Job.objects.filter(id=int(R["id"])).values(*utils.JobFields.fields)[0]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2493
Type: missing_optimization
Code: job = Job.objects.filter(id=int(R["id"])).values(*utils.JobFields.fields)[0]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2585
Type: missing_optimization
Code: Job.objects.filter(parent_id=job.id).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2618
Type: missing_optimization
Code: job = Job.objects.filter(id=int(R["job_id"])).values()[0]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/schedhuler/views.py:2619
Type: missing_optimization
Code: P["model"].objects.filter(parent_id=job["id"]).delete()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/auth.py:31
Type: missing_optimization
Code: People.objects.filter(id=response["user"].id).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/auth.py:38
Type: missing_optimization
Code: People.objects.filter(id=response["user"].id).update(deviceid=-1)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/mutations.py:183
Type: missing_optimization
Code: people_location = People.objects.filter(id=user.id).values_list('people_extras__enable_gps', flat=True).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/mutations.py:184
Type: missing_optimization
Code: bt_location_enable = Bt.objects.filter(id=user.bu_id).values_list('gpsenable', flat=True).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/bt_queries.py:212
Type: missing_optimization
Code: user = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/bt_queries.py:235
Type: missing_optimization
Code: DownTimeHistory.objects.filter(client_id=validated.client_id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:154
Type: missing_optimization
Code: p = People.objects.filter(id=validated.peopleid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:159
Type: missing_optimization
Code: updated = Wom.objects.filter(uuid=validated.wom_uuid).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:164
Type: missing_optimization
Code: Wom.objects.filter(id=wom.id).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:195
Type: missing_optimization
Code: p = People.objects.filter(id=validated.peopleid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:199
Type: missing_optimization
Code: updated = Wom.objects.filter(uuid=validated.wom_uuid).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:230
Type: missing_optimization
Code: p = People.objects.filter(id=validated.peopleid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/queries/workpermit_queries.py:231
Type: missing_optimization
Code: Wom.objects.filter(uuid=validated.wom_uuid).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/querys.py:132
Type: missing_optimization
Code: DownTimeHistory.objects.filter(client_id=client_id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/rest_service/views.py:16
Type: missing_optimization
Code: queryset = model.objects.filter(mdtz__gt=last_update)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/types.py:258
Type: missing_optimization
Code: return JobneedDetails.objects.filter(jobneed=self)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:202
Type: missing_optimization
Code: if not TypeAssist.objects.filter(id=record["ownername_id"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:208
Type: missing_optimization
Code: correct_ta = TypeAssist.objects.filter(tacode=ownername).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:228
Type: missing_optimization
Code: if model.objects.filter(uuid=record["uuid"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:229
Type: missing_optimization
Code: model.objects.filter(uuid=record["uuid"]).update(**record)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:231
Type: missing_optimization
Code: obj = model.objects.filter(uuid=record["uuid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:247
Type: missing_optimization
Code: if JobneedDetails.objects.filter(uuid=detail_cleaned.get("uuid")).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:248
Type: missing_optimization
Code: JobneedDetails.objects.filter(uuid=detail_cleaned["uuid"]).update(**detail_cleaned)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:414
Type: missing_optimization
Code: Wom.objects.filter(parent_id=wom.id)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:513
Type: missing_optimization
Code: Wom.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:607
Type: missing_optimization
Code: bet_objs = Tracking.objects.filter(reference=obj.uuid).order_by("receiveddate")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:634
Type: missing_optimization
Code: Jobneed.objects.filter(id=scheduletask["id"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:646
Type: missing_optimization
Code: f'record after updation {pformat(Jobneed.objects.filter(id =scheduletask["id"]).values())}'

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:650
Type: missing_optimization
Code: JND = JobneedDetails.objects.filter(jobneed_id=scheduletask["id"]).values()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:799
Type: missing_optimization
Code: between_latlngs = Tracking.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:1033
Type: missing_optimization
Code: site_crisis_obj = TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/service/utils.py:1150
Type: missing_optimization
Code: assetobjs = Asset.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/consumers.py:129
Type: missing_optimization
Code: recent_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/services/event_capture.py:325
Type: missing_optimization
Code: recent_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/services/visual_diff_processor.py:97
Type: missing_optimization
Code: existing_baseline = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/services/visual_diff_processor.py:305
Type: missing_optimization
Code: baselines = StreamEvent.objects.filter(**query_filters).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/services/visual_diff_processor.py:318
Type: missing_optimization
Code: old_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:70
Type: missing_optimization
Code: recent_events = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:245
Type: missing_optimization
Code: throughput_data = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:255
Type: missing_optimization
Code: error_data = StreamEvent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:336
Type: missing_optimization
Code: 'total_scenarios': TestScenario.objects.filter(is_active=True).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:337
Type: missing_optimization
Code: 'active_runs': TestRun.objects.filter(status='running').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:338
Type: missing_optimization
Code: 'runs_24h': TestRun.objects.filter(started_at__gte=last_24h).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:339
Type: missing_optimization
Code: 'runs_7d': TestRun.objects.filter(started_at__gte=last_7d).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:340
Type: missing_optimization
Code: 'events_24h': StreamEvent.objects.filter(timestamp__gte=last_24h).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:341
Type: missing_optimization
Code: 'events_7d': StreamEvent.objects.filter(timestamp__gte=last_7d).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:342
Type: missing_optimization
Code: 'anomalies_24h': AnomalyOccurrence.objects.filter(created_at__gte=last_24h).count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/streamlab/views.py:343
Type: missing_optimization
Code: 'active_anomalies': AnomalySignature.objects.filter(status='active').count(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/management/commands/seed_wellness_content.py:99
Type: missing_optimization
Code: system_user = User.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/management/commands/seed_wellness_content.py:106
Type: missing_optimization
Code: system_user = User.objects.filter(tenant=tenant).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/management/commands/seed_wellness_content.py:123
Type: missing_optimization
Code: existing_content = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:64
Type: missing_optimization
Code: content_queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:208
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:255
Type: missing_optimization
Code: content_queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:342
Type: missing_optimization
Code: user_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:357
Type: missing_optimization
Code: recent_category_views = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:405
Type: missing_optimization
Code: user_interactions = WellnessContentInteraction.objects.filter(user=user)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:458
Type: missing_optimization
Code: content_queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:660
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:783
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:990
Type: missing_optimization
Code: urgent_content = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/services/content_delivery.py:1012
Type: missing_optimization
Code: follow_up_content = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/signals.py:250
Type: missing_optimization
Code: inactive_users = WellnessUserProgress.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:134
Type: missing_optimization
Code: content_count = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:234
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:274
Type: missing_optimization
Code: queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:295
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:460
Type: missing_optimization
Code: queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:487
Type: missing_optimization
Code: queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:587
Type: missing_optimization
Code: recent_entries = JournalEntry.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:604
Type: missing_optimization
Code: interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:628
Type: missing_optimization
Code: queryset = WellnessContent.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:639
Type: missing_optimization
Code: recent_interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/wellness/views.py:853
Type: missing_optimization
Code: interactions = WellnessContentInteraction.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/admin.py:27
Type: missing_optimization
Code: return self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/admin.py:35
Type: missing_optimization
Code: return self.model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/admin.py:256
Type: missing_optimization
Code: if not wom.Vendor.objects.filter(id=row["ID*"]).exists():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:69
Type: missing_optimization
Code: self.fields["type"].queryset = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:158
Type: missing_optimization
Code: self.fields["categories"].choices = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:171
Type: missing_optimization
Code: self.fields["location"].queryset = Location.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:174
Type: missing_optimization
Code: self.fields["vendor"].queryset = Vendor.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:178
Type: missing_optimization
Code: self.fields["qset"].queryset = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:238
Type: missing_optimization
Code: QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:248
Type: missing_optimization
Code: self.fields["vendor"].queryset = Vendor.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:330
Type: missing_optimization
Code: self.fields["approverfor"].choices = om.TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:336
Type: missing_optimization
Code: self.fields["people"].queryset = People.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:409
Type: missing_optimization
Code: self.fields["qset"].queryset = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/forms.py:416
Type: missing_optimization
Code: self.fields["vendor"].queryset = Vendor.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/managers.py:239
Type: missing_optimization
Code: is_approver = Approver.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/managers.py:337
Type: missing_optimization
Code: sections_qset = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/managers.py:361
Type: missing_optimization
Code: sections_qset = QuestionSet.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services.py:36
Type: missing_optimization
Code: model_class.objects.filter(client_id=S["client_id"], enable=True)

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services.py:68
Type: missing_optimization
Code: qset = model_class.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services.py:119
Type: missing_optimization
Code: is_approver = Approver.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services.py:240
Type: missing_optimization
Code: model_class.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services.py:299
Type: missing_optimization
Code: typeassist_model.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/services/work_order_service.py:569
Type: missing_optimization
Code: 'valid_vendor': lambda data: Vendor.objects.filter(id=data.vendor_id).exists(),

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/signals.py:16
Type: missing_optimization
Code: sender.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/signals.py:28
Type: missing_optimization
Code: sender.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:31
Type: missing_optimization
Code: if wo := Wom.objects.filter(id=id).first():

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:75
Type: missing_optimization
Code: w = Wom.objects.filter(uuid=womuuid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:93
Type: missing_optimization
Code: w = Wom.objects.filter(uuid=womuuid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:111
Type: missing_optimization
Code: w = Wom.objects.filter(uuid=womuuid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:119
Type: missing_optimization
Code: w = Wom.objects.filter(uuid=womuuid).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:201
Type: missing_optimization
Code: wom = Wom.objects.filter(parent_id=sla.id).order_by("-id")[1]

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:202
Type: missing_optimization
Code: uptime_score = WomDetails.objects.filter(wom_id=wom.id)[2].answer

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:231
Type: missing_optimization
Code: qsb_obj = QuestionSetBelonging.objects.filter(id=qsb_id).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:275
Type: missing_optimization
Code: if childwom := Wom.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:425
Type: missing_optimization
Code: latest_report = Wom.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:435
Type: missing_optimization
Code: report = Wom.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/utils.py:470
Type: missing_optimization
Code: data = People.objects.filter(peoplecode=people_code).values(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:193
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(workstatus="CLOSED")

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:416
Type: missing_optimization
Code: ownername = TypeAssist.objects.filter(tacode="WOMDETAILS").first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:492
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:516
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:542
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:671
Type: missing_optimization
Code: rwp_seqno = Wom.objects.filter(parent_id=R["wom_id"]).count() + 1

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:819
Type: missing_optimization
Code: if childwom := Wom.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:866
Type: missing_optimization
Code: qsb_obj = QuestionSetBelonging.objects.filter(id=qsb_id).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:954
Type: missing_optimization
Code: wp = Wom.objects.filter(id=R["womid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:955
Type: missing_optimization
Code: p = People.objects.filter(id=R["peopleid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:963
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1082
Type: missing_optimization
Code: wp = Wom.objects.filter(id=R["womid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1083
Type: missing_optimization
Code: p = People.objects.filter(id=R["peopleid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1090
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1117
Type: missing_optimization
Code: Wom.objects.filter(id=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1143
Type: missing_optimization
Code: wp = Wom.objects.filter(id=R["womid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1152
Type: missing_optimization
Code: p = People.objects.filter(id=R["peopleid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1178
Type: missing_optimization
Code: p = People.objects.filter(id=R["peopleid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1185
Type: missing_optimization
Code: Wom.objects.filter(uuid=R["womid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1232
Type: missing_optimization
Code: wp = Wom.objects.filter(uuid=R["womid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1237
Type: missing_optimization
Code: p = People.objects.filter(id=R["peopleid"]).first()

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1405
Type: missing_optimization
Code: Wom.objects.filter(id=R["slaid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/work_order_management/views.py:1420
Type: missing_optimization
Code: Wom.objects.filter(id=R["slaid"]).update(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/forms.py:70
Type: missing_optimization
Code: self.fields["ticketcategory"].queryset = TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/managers.py:312
Type: missing_optimization
Code: TypeAssist.objects.filter(

[MEDIUM] /Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/signals.py:18
Type: missing_optimization
Code: sender.objects.filter(

================================================================================
RECOMMENDATIONS
================================================================================

1. Add select_related() for ForeignKey fields accessed in templates
2. Add prefetch_related() for reverse ForeignKey and ManyToMany fields
3. Implement get_queryset() in all ListView classes
4. Add list_select_related in ModelAdmin classes with list_display
5. Use Django Debug Toolbar or django-silk to verify query counts
