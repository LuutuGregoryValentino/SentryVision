from marshmallow import Schema, fields


class DeviceStatusUpdateSchema(Schema):
    device_name = fields.String(load_default=None, allow_none=True)
    status = fields.String(required=True)
    metric_name = fields.String(load_default=None, allow_none=True)
    metric_value = fields.Float(load_default=None, allow_none=True)
    metric_unit = fields.String(load_default=None, allow_none=True)
    metadata = fields.Dict(load_default=dict)
