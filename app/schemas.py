from marshmallow import Schema, ValidationError, fields, pre_load, validates_schema


class FacialRecognitionSchema(Schema):
    label = fields.String(required=True)

    @pre_load
    def normalize_edge_impulse_payload(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError("Payload must be a JSON object.")

        if "label" in data:
            return data

        if "detected_label" in data:
            data["label"] = data["detected_label"]
            return data

        if "classification" in data and isinstance(data["classification"], dict):
            label, _score = max(data["classification"].items(), key=lambda item: item[1])
            data["label"] = label
            return data

        return data

    @validates_schema
    def validate_label(self, data, **kwargs):
        label = data.get("label")
        if label is None or not label.strip():
            raise ValidationError({"label": ["Detected label is required."]})


class DeviceStatusUpdateSchema(Schema):
    status = fields.String(required=True)
    metric_name = fields.String(load_default=None, allow_none=True)
    metric_value = fields.Float(load_default=None, allow_none=True)
    metric_unit = fields.String(load_default=None, allow_none=True)
    metadata = fields.Dict(load_default=dict)
