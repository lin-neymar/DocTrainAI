"""系统品牌与个人主题 Schema。"""

from pydantic import BaseModel, Field


class BrandPublicData(BaseModel):
    site_name: str
    login_subtitle: str
    has_logo: bool


class BrandUpdate(BaseModel):
    site_name: str = Field(min_length=1, max_length=128)
    login_subtitle: str = Field(min_length=1, max_length=256)


class ThemeUpdate(BaseModel):
    """个人主题主色；传 null 表示恢复默认。"""

    theme_primary: str | None = Field(default=None, max_length=16)
