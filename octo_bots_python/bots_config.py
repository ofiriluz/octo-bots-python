from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr


class BotsSettings(BaseModel):
    parallel_background_jobs: int = Field(default=10, alias="parallel-background-jobs")
    bots_endpoint: str = Field(default="/events", alias="bots-endpoint")
    client_validity_time_minutes: int = Field(default=10, alias="client-validity-time-minutes")
    parallel_bots: bool = Field(default=True, alias="parallel-bots")


class BotsGithubCredentialsConfig(BaseModel):
    api_url: str = Field(default="https://api.github.com", alias="api-url")
    app_name: str = Field(alias="app-name")
    app_id: Optional[str] = Field(alias="app-id")
    client_id: Optional[str] = Field(alias="client-id")
    client_secret: Optional[SecretStr] = Field(alias="client-secret")
    private_key: Optional[SecretStr] = Field(alias="private-key")
    webhook_secret: Optional[SecretStr] = Field(alias="webhook-secret")


class BotsCheckmarxCredentialsConfig(BaseModel):
    api_url: str = Field(alias="api-url")
    username: Optional[str] = Field()
    password: Optional[SecretStr] = Field()
    grant_type: Optional[str] = Field(alias="grant-type")
    scope: Optional[str] = Field()
    client_id: Optional[str] = Field(alias="client-id")
    client_secret: Optional[SecretStr] = Field(alias="client-secret")
    team_full_name: Optional[str] = Field(alias="team-full-name")


BotsCredentialsConfig = Union[BotsGithubCredentialsConfig, BotsCheckmarxCredentialsConfig]


class BotsCredsType(str, Enum):
    Github = "github-app-credentials"
    Checkmarx = "checkmarx-app-credentials"


class BotDescription(BaseModel):
    name: str
    parallel: bool = Field(default=True)
    operations: List[Dict[str, Dict[str, Any]]] = Field(default=[])
    filters: List[Dict[str, Dict[str, Any]]] = Field(default=[])


class BotsDescription(BaseModel):
    bots: List[BotDescription]


class BackgroundJobDescription(BaseModel):
    name: str
    every: str
    parallel: bool = Field(default=True)
    operations: List[Dict[str, Dict[str, Any]]] = Field(default=[])
    filters: List[Dict[str, Dict[str, Any]]] = Field(default=[])


class BackgroundJobsDescription(BaseModel):
    background_jobs: List[BackgroundJobDescription] = Field(alias="background-jobs")


class BotsConfig(BaseModel):
    settings: BotsSettings = Field()
    credentials: Dict[BotsCredsType, BotsCredentialsConfig] = Field()
    bots: List[Union[str, BotDescription]] = Field()
    background_jobs: List[Union[str, BackgroundJobDescription]] = Field(alias="background-jobs")
