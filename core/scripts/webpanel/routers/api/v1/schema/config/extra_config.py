from pydantic import BaseModel, field_validator, Field

VALID_PROTOCOLS = ("vmess://", "vless://", "ss://", "trojan://")

class ExtraConfigBase(BaseModel):
    name: str = Field(..., min_length=1, description="A unique name for the configuration.")
    uri: str = Field(..., description="The proxy URI.")

    @field_validator('uri')
    def validate_uri_protocol(cls, v):
        if not any(v.startswith(protocol) for protocol in VALID_PROTOCOLS):
            raise ValueError(f"Invalid URI. Must start with one of {', '.join(VALID_PROTOCOLS)}")
        return v

class AddExtraConfigBody(ExtraConfigBase):
    pass

class DeleteExtraConfigBody(BaseModel):
    name: str

class ExtraConfigResponse(ExtraConfigBase):
    pass

ExtraConfigListResponse = list[ExtraConfigResponse]