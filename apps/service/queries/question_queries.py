import graphene
import json
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from graphql import GraphQLError
from apps.service.pydantic_schemas.question_schema import (
    QuestionModifiedSchema,
    QuestionSetModifiedSchema,
    QuestionSetBelongingModifiedSchema,
)
from apps.service.types import SelectOutputType
from logging import getLogger
from apps.core import utils
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.decorators import require_authentication, require_tenant_access

log = getLogger("mobile_service_log")


class QuestionQueries(graphene.ObjectType):
    get_questionsmodifiedafter = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True), 
        clientid=graphene.Int(required=True)
    )

    get_qsetmodifiedafter = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True),
        buid=graphene.Int(required=True),
        clientid=graphene.Int(required=True),
        peopleid=graphene.Int(required=True)
    )

    get_qsetbelongingmodifiedafter = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True),
        buid=graphene.Int(required=True),
        clientid=graphene.Int(required=True),
        peopleid=graphene.Int(required=True),
        includeDependencyLogic=graphene.Boolean(default_value=False)  # Optional: include dependency processing
    )

    get_questionset_with_conditional_logic = graphene.Field(
        SelectOutputType,
        qset_id=graphene.Int(required=True),
        clientid=graphene.Int(required=True),
        buid=graphene.Int(required=True)
    )

    @staticmethod
    @require_tenant_access
    def resolve_get_questionsmodifiedafter(self, info, mdtz, ctzoffset, clientid):
        try:
            log.info("request for get_questions_modified_after")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz, 
                'ctzoffset': ctzoffset, 
                'clientid': clientid
            }
            validated = QuestionModifiedSchema(**filter_data)
            data = Question.objects.get_questions_modified_after(
                mdtz=validated.mdtz, clientid=validated.clientid
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_questionsmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Question.DoesNotExist:
            log.warning("Questions not found")
            raise GraphQLError("Questions not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_questionsmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_qsetmodifiedafter(self, info, mdtz, ctzoffset, buid, clientid, peopleid):
        try:
            log.info("request for get_questionset_modified_after")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid,
                'clientid': clientid,
                'peopleid': peopleid
            }
            validated = QuestionSetModifiedSchema(**filter_data)
            data = QuestionSet.objects.get_qset_modified_after(
                mdtz=validated.mdtz,
                buid=validated.buid,
                clientid=validated.clientid,
                peopleid=validated.peopleid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_qsetmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except QuestionSet.DoesNotExist:
            log.warning("Question sets not found")
            raise GraphQLError("Question sets not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_qsetmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_qsetbelongingmodifiedafter(self, info, mdtz, ctzoffset, buid, clientid, peopleid, includeDependencyLogic=False):
        try:
            log.info(f"request for get_questionsetbelonging_modified_after (includeDependencyLogic={includeDependencyLogic})")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid,
                'clientid': clientid,
                'peopleid': peopleid
            }
            validated = QuestionSetBelongingModifiedSchema(**filter_data)
            data = QuestionSetBelonging.objects.get_modified_after(
                mdtz=validated.mdtz, buid=validated.buid
            )
            
            # If dependency logic is requested, enhance the data with dependency analysis
            if includeDependencyLogic:
                # Convert queryset to list for processing
                data_list = list(data)
                log.info(f"Processing {len(data_list)} records for dependency analysis")
                
                # Group by questionset for dependency analysis
                qset_groups = {}
                for record in data_list:
                    qset_id = record.get('qset_id')
                    if qset_id not in qset_groups:
                        qset_groups[qset_id] = []
                    qset_groups[qset_id].append(record)
                
                # Add dependency metadata to each questionset group
                enhanced_records = []
                for qset_id, questions in qset_groups.items():
                    # Use the existing get_questions_with_logic method for structured output
                    try:
                        logic_data = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)
                        dependency_map = logic_data.get('dependency_map', {})
                        has_conditional_logic = logic_data.get('has_conditional_logic', False)
                        
                        # Ensure dependency_map is JSON serializable
                        clean_dependency_map = {}
                        if isinstance(dependency_map, dict):
                            for dep_key, dep_value in dependency_map.items():
                                if isinstance(dep_value, dict):
                                    clean_dep_value = {}
                                    for k, v in dep_value.items():
                                        if isinstance(v, (dict, list, str, int, float, bool, type(None))):
                                            clean_dep_value[k] = v
                                        else:
                                            clean_dep_value[k] = str(v) if v is not None else None
                                    clean_dependency_map[str(dep_key)] = clean_dep_value
                                else:
                                    clean_dependency_map[str(dep_key)] = str(dep_value) if dep_value is not None else None
                        
                        # Add metadata to each question record
                        for record in questions:
                            record['dependency_map'] = clean_dependency_map
                            record['has_conditional_logic'] = bool(has_conditional_logic)
                            enhanced_records.append(record)
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as dep_error:
                        log.warning(f"Could not process dependencies for qset {qset_id}: {str(dep_error)}")
                        # Add records without dependency data
                        for record in questions:
                            record['dependency_map'] = {}
                            record['has_conditional_logic'] = False
                            enhanced_records.append(record)
                
                data = enhanced_records
                log.info(f"Enhanced {len(data)} records with dependency logic")
                
                # Handle list data manually since utils.get_select_output expects QuerySet
                # Ensure all data is JSON serializable
                serializable_data = []
                for record in data:
                    try:
                        # Convert any non-serializable objects to strings/dicts
                        clean_record = {}
                        for key, value in record.items():
                            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                                clean_record[key] = value
                            else:
                                # Convert complex objects to string representation
                                clean_record[key] = str(value) if value is not None else None
                        serializable_data.append(clean_record)
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as serialize_error:
                        log.warning(f"Could not serialize record: {str(serialize_error)}")
                        # Skip problematic records
                        continue
                
                records = json.dumps(serializable_data, default=str, ensure_ascii=False)
                count = len(serializable_data)
                msg = f"Total {count} records with conditional logic fetched successfully!"
            else:
                # Use standard utils function for QuerySet data
                records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_qsetbelongingmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except QuestionSetBelonging.DoesNotExist:
            log.warning("QuestionSet belongings not found")
            raise GraphQLError("QuestionSet belongings not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_qsetbelongingmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")
        except (TypeError, KeyError, json.JSONDecodeError) as e:
            log.error("Data serialization error in get_qsetbelongingmodifiedafter", exc_info=True)
            raise GraphQLError("Data processing failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_questionset_with_conditional_logic(self, info, qset_id, clientid, buid):
        """
        Dedicated GraphQL resolver for fetching a questionset with full conditional logic support.
        Returns structured data optimized for mobile app dependency evaluation.

        ENHANCED (2025-10-03):
        - Adds validation warnings for invalid dependencies
        - Detects circular dependencies
        - Validates dependency ordering (must come before)
        - Supports both old 'question_id' and new 'qsb_id' keys for backward compatibility

        DEPRECATION WARNING:
        The 'question_id' key in display_conditions.depends_on actually holds a
        QuestionSetBelonging ID, not a Question ID. Mobile apps should migrate to
        using 'qsb_id' for clarity. Both keys are supported for 2 release cycles.
        """
        try:
            log.info(f"request for get_questionset_with_conditional_logic (qset_id={qset_id})")

            # Use the enhanced manager method with validation
            logic_data = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)

            # Check for validation warnings
            if logic_data.get('validation_warnings'):
                # Log warnings but don't fail the request
                warnings_count = len(logic_data['validation_warnings'])
                critical_warnings = [
                    w for w in logic_data['validation_warnings']
                    if w.get('severity') == 'critical'
                ]

                log.warning(
                    f"Questionset {qset_id} has {warnings_count} validation warnings "
                    f"({len(critical_warnings)} critical)",
                    extra={
                        'qset_id': qset_id,
                        'warnings': logic_data['validation_warnings']
                    }
                )

                # Add deprecation warning if using old 'question_id' key
                has_old_key = any(
                    q.get('display_conditions', {}).get('depends_on', {}).get('question_id')
                    for q in logic_data.get('questions', [])
                )

                if has_old_key:
                    log.info(
                        f"DEPRECATION WARNING: Questionset {qset_id} uses deprecated 'question_id' key. "
                        f"Mobile apps should migrate to 'qsb_id' key. "
                        f"Support for 'question_id' will be removed in 3 releases.",
                        extra={'qset_id': qset_id}
                    )

            # The get_questions_with_logic method returns:
            # {
            #     "questions": [...],                 # List of questions with all fields
            #     "dependency_map": {...},            # Structured dependency information
            #     "has_conditional_logic": bool,      # Whether this questionset has dependencies
            #     "validation_warnings": [...]        # Optional: validation issues
            # }

            # Convert to format expected by GraphQL SelectOutputType
            records = [logic_data]  # Wrap the structured response
            count = 1
            msg = f"Questionset {qset_id} with conditional logic retrieved successfully"

            if logic_data.get('validation_warnings'):
                msg += f" ({len(logic_data['validation_warnings'])} validation warnings)"

            log.info(f"Questionset {qset_id}: {len(logic_data.get('questions', []))} questions, "
                    f"conditional logic: {logic_data.get('has_conditional_logic', False)}, "
                    f"warnings: {len(logic_data.get('validation_warnings', []))}")

            return SelectOutputType(nrows=count, records=records, msg=msg)

        except ValidationError as ve:
            log.error("Validation error in get_questionset_with_conditional_logic", exc_info=True)
            raise GraphQLError(f"Invalid question set ID: {str(ve)}")
        except QuestionSetBelonging.DoesNotExist:
            log.warning(f"QuestionSet {qset_id} not found")
            raise GraphQLError("Question set not found")
        except (DatabaseError, IntegrityError) as e:
            log.error(f"Database error in get_questionset_with_conditional_logic for qset_id={qset_id}", exc_info=True)
            raise GraphQLError("Database operation failed")
        except (TypeError, KeyError, json.JSONDecodeError) as e:
            log.error(f"Data processing error in get_questionset_with_conditional_logic for qset_id={qset_id}", exc_info=True)
            raise GraphQLError("Data processing failed")
