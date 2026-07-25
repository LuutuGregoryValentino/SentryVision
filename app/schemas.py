from marshmallow import EXCLUDE, Schema, ValidationError, fields, pre_load


def _normalize_label(label):
    if not isinstance(label, str):
        return label
    return " ".join(label.strip().split())


class FacialRecognitionSchema(Schema):
    label = fields.String(load_default=None, allow_none=True)
    features = fields.Raw(load_default=None, allow_none=True)

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def normalize_edge_impulse_payload(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError("Payload must be a JSON object.")

        if "label" in data:
            data["label"] = _normalize_label(data["label"])
            return data

        if "detected_label" in data:
            data["label"] = _normalize_label(data["detected_label"])
            return data

        if "classification" in data and isinstance(data["classification"], dict):
            label, _score = max(data["classification"].items(), key=lambda item: item[1])
            data["label"] = _normalize_label(label)
            return data

        return data


class DeviceStatusUpdateSchema(Schema):
    status = fields.String(required=True)
    metric_name = fields.String(load_default=None, allow_none=True)
    metric_value = fields.Float(load_default=None, allow_none=True)
    metric_unit = fields.String(load_default=None, allow_none=True)
    metadata = fields.Dict(load_default=dict)
