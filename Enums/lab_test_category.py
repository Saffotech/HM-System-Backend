import enum


class LabTestCategory(str, enum.Enum):
    LABORATORY = "Laboratory"
    RADIOLOGY = "Radiology"
    CARDIOLOGY = "Cardiology"


_CATEGORY_REQUIRES_SAMPLE: dict[LabTestCategory, bool] = {
    LabTestCategory.LABORATORY: True,
    LabTestCategory.RADIOLOGY: False,
    LabTestCategory.CARDIOLOGY: False,
}


def category_requires_sample(category: str) -> bool:
    return _CATEGORY_REQUIRES_SAMPLE[LabTestCategory(category)]


def list_lab_test_categories() -> list[dict]:
    return [
        {
            "value": category.value,
            "label": category.value,
            "requires_sample": _CATEGORY_REQUIRES_SAMPLE[category],
        }
        for category in LabTestCategory
    ]
