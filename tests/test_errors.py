from mednexa.core.errors import (ConflictError, DataUnavailableError, NotFoundError,
                                 PermissionDeniedError, ServiceError, ValidationError)


def test_error_envelope_matches_feature2_contract():
    e = ServiceError("Plan not found", code="PLAN_NOT_FOUND")
    assert e.to_dict() == {"error": {"code": "PLAN_NOT_FOUND", "message": "Plan not found"}}


def test_validation_error_carries_field_errors():
    e = ValidationError(field_errors={"name": "Required"})
    assert e.code == "VALIDATION_ERROR" and e.field_errors == {"name": "Required"}
    assert e.to_dict()["error"]["details"] == {"fields": {"name": "Required"}}


def test_subclasses_have_user_messages():
    for cls in (NotFoundError, PermissionDeniedError, ConflictError, DataUnavailableError):
        err = cls()
        assert isinstance(err, ServiceError) and err.user_message and "Traceback" not in err.user_message
