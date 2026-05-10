from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

class ColumnInfo(BaseModel):
    name: str
    inferred_type: str
    missing_count: int

class SheetInfo(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]
    rows: List[dict] = Field(default_factory=list)
    preview_rows: List[dict]

class WorkbookUploadResponse(BaseModel):
    workbook_id: str
    sheets: List[SheetInfo]

class ColumnMapping(BaseModel):
    feature_columns: List[str]
    label_column: Optional[str] = None
    id_column: Optional[str] = None
    exclude_columns: List[str] = Field(default_factory=list)

class AlgorithmType(str, Enum):
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    SVM = "svm"
    LOGISTIC_REGRESSION = "logistic_regression"
    LINEAR_REGRESSION = "linear_regression"

class PreprocessingSettings(BaseModel):
    handle_missing: str = "mean" # mean, median, drop, zero
    normalization: str = "minmax" # minmax, standard, none
    outlier_removal: bool = False
    categorical_encoding: str = "label" # label, onehot
    calculate_importance: bool = True
    feature_selection_threshold: Optional[float] = None # e.g., 0.05

class JobRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    mapping: ColumnMapping
    algorithm: AlgorithmType = AlgorithmType.RANDOM_FOREST
    params: dict = Field(default_factory=dict)
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    run_cleansing: bool = True
    run_feature_selection: bool = True
    run_ml: bool = True

class JobResponse(BaseModel):
    job_id: str
    status: str
    metadata: dict = Field(default_factory=dict)


class ReviewAssessment(str, Enum):
    KEEP = "keep"
    NEEDS_IMPROVEMENT = "needs_improvement"
    DISABLE = "disable"
    REVIEW_MANUALLY = "review_manually"
    NEEDS_MORE_DATA = "needs_more_data"


class ReviewActionType(str, Enum):
    REMOVE_OUTLIERS = "remove_outliers"
    EXCLUDE_ISLANDS = "exclude_islands"
    DROP_FEATURES = "drop_features"
    CHANGE_MISSING = "change_missing"
    CHANGE_NORMALIZATION = "change_normalization"
    ADJUST_THRESHOLD = "adjust_threshold"
    SWITCH_ALGORITHM = "switch_algorithm"
    REVIEW_MANUALLY = "review_manually"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISCARDED = "discarded"


class ConfidenceStats(BaseModel):
    mean: float = 0.0
    minimum: float = 0.0
    p10: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    maximum: float = 0.0


class DistributionItem(BaseModel):
    value: str
    count: int
    ratio: float = 0.0


class ScoreItem(BaseModel):
    feature: str
    score: float


class ClusterSummary(BaseModel):
    cluster_id: str
    size: int
    is_island: bool = False
    review_priority: int = 0
    nearest_major_class: Optional[str] = None


class RepresentativeRow(BaseModel):
    row_id: int
    values: Dict[str, Any] = Field(default_factory=dict)


class ReviewAction(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    action: ReviewActionType
    target: Any = None
    reason: str = ""
    expected_effect: Optional[str] = None
    safe_to_apply: bool = False
    params: Dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.PENDING


class ReviewSummary(BaseModel):
    job_id: str
    workbook_id: str
    sheet_name: str
    algorithm: str
    row_count: int
    feature_count: int
    feature_columns: List[str] = Field(default_factory=list)
    label_column: Optional[str] = None
    missing_rate: float = 0.0
    outlier_rate: float = 0.0
    island_rate: float = 0.0
    class_distribution: List[DistributionItem] = Field(default_factory=list)
    prediction_confidence: ConfidenceStats = Field(default_factory=ConfidenceStats)
    feature_importance_top: List[ScoreItem] = Field(default_factory=list)
    cluster_summary: List[ClusterSummary] = Field(default_factory=list)
    representative_rows: List[RepresentativeRow] = Field(default_factory=list)
    quality_flags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewResult(BaseModel):
    assessment: ReviewAssessment = ReviewAssessment.REVIEW_MANUALLY
    confidence: float = 0.0
    blocking_factors: List[str] = Field(default_factory=list)
    recommended_actions: List[ReviewAction] = Field(default_factory=list)
    reason: str = ""
    safe_to_apply: bool = False
    source: str = "openai"
    summary: Optional[ReviewSummary] = None


class RerunRequest(BaseModel):
    proposal_ids: List[str] = Field(default_factory=list)


class ProposalListResponse(BaseModel):
    job_id: str
    proposals: List[ReviewAction] = Field(default_factory=list)


class ComparisonResponse(BaseModel):
    job_id: str
    before: ReviewSummary
    after: ReviewSummary
    deltas: Dict[str, Any] = Field(default_factory=dict)
    applied_proposals: List[ReviewAction] = Field(default_factory=list)
    accepted: bool = False


class BoundaryAxisRange(BaseModel):
    label: str
    minimum: float
    maximum: float


class BoundaryGridCell(BaseModel):
    x: float
    y: float
    predicted_label: Optional[str] = None
    confidence: float = 0.0


class BoundaryPoint(BaseModel):
    row_id: int
    x: float
    y: float
    true_label: Optional[str] = None
    predicted_label: Optional[str] = None
    confidence: float = 0.0
    is_misclassified: bool = False
    is_outlier: bool = False
    is_island: bool = False
    review_priority: int = 0
    cluster_id: Optional[str] = None


class BoundarySnapshot(BaseModel):
    job_id: str
    projection: str = "pca"
    x_axis: BoundaryAxisRange
    y_axis: BoundaryAxisRange
    grid_resolution: int = 40
    grid_step_x: float = 0.0
    grid_step_y: float = 0.0
    class_labels: List[str] = Field(default_factory=list)
    explained_variance_ratio: List[float] = Field(default_factory=list)
    points: List[BoundaryPoint] = Field(default_factory=list)
    grid: List[BoundaryGridCell] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
