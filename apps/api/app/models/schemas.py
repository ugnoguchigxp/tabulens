from enum import Enum
from typing import Any, Dict, List, Literal, Optional
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
    feature_columns: List[str] = Field(default_factory=list)
    label_column: Optional[str] = None
    id_column: Optional[str] = None
    exclude_columns: List[str] = Field(default_factory=list)
    user_id_column: Optional[str] = None
    item_id_column: Optional[str] = None
    rating_column: Optional[str] = None
    timestamp_column: Optional[str] = None


class UseCaseType(str, Enum):
    CLASSIFICATION = "classification"
    PREDICTION = "prediction"
    ANOMALY_DETECTION = "anomaly_detection"
    RECOMMENDATION = "recommendation"
    CLUSTERING = "clustering"
    NOISE_REDUCTION = "noise_reduction"

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


class ModelWorkflowRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    source_job_id: Optional[str] = None
    use_case: UseCaseType = UseCaseType.CLASSIFICATION
    mapping: ColumnMapping = Field(default_factory=ColumnMapping)
    algorithm: str = "auto"
    params: dict = Field(default_factory=dict)
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)


class WorkflowMetrics(BaseModel):
    values: dict = Field(default_factory=dict)


class ModelWorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    use_case: UseCaseType
    rows: List[dict] = Field(default_factory=list)
    metrics: WorkflowMetrics = Field(default_factory=WorkflowMetrics)
    metadata: dict = Field(default_factory=dict)


class WorkflowRowsResponse(BaseModel):
    workflow_id: str
    rows: List[dict] = Field(default_factory=list)


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


class ModelReviewAssessment(str, Enum):
    PASS = "pass"
    NEEDS_IMPROVEMENT = "needs_improvement"
    REJECT = "reject"
    REVIEW_MANUALLY = "review_manually"
    NEEDS_MORE_DATA = "needs_more_data"


class ModelReviewActionType(str, Enum):
    ADJUST_DECISION_THRESHOLD = "adjust_decision_threshold"
    REBALANCE_CLASSES = "rebalance_classes"
    ENABLE_STRATIFIED_SPLIT = "enable_stratified_split"
    INCREASE_TEST_SIZE = "increase_test_size"
    SWITCH_ALGORITHM = "switch_algorithm"
    TUNE_HYPERPARAMETERS = "tune_hyperparameters"
    DROP_LEAKY_FEATURES = "drop_leaky_features"
    NORMALIZE_FEATURES = "normalize_features"
    ADJUST_CONTAMINATION = "adjust_contamination"
    ADJUST_CLUSTER_COUNT = "adjust_cluster_count"
    ADJUST_DBSCAN_EPS = "adjust_dbscan_eps"
    SWITCH_TO_PREVIEW_MODE = "switch_to_preview_mode"
    REVIEW_LABEL_QUALITY = "review_label_quality"
    COLLECT_MORE_DATA = "collect_more_data"


class ModelReviewAction(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    action: ModelReviewActionType
    target: Any = None
    reason: str = ""
    expected_effect: Optional[str] = None
    safe_to_apply: bool = False
    params: Dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.PENDING


class ModelReviewSummary(BaseModel):
    workflow_id: str
    source_job_id: Optional[str] = None
    workbook_id: str
    sheet_name: str
    use_case: UseCaseType
    algorithm: str
    row_count: int
    train_count: int = 0
    test_count: int = 0
    unused_count: int = 0
    feature_columns: List[str] = Field(default_factory=list)
    label_column: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    quality_flags: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    feature_importance: List[Dict[str, Any]] = Field(default_factory=list)
    sample_errors: List[Dict[str, Any]] = Field(default_factory=list)
    sample_low_confidence: List[Dict[str, Any]] = Field(default_factory=list)
    sample_outliers: List[Dict[str, Any]] = Field(default_factory=list)
    boundary_summary: Dict[str, Any] = Field(default_factory=dict)
    split_summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelReviewResult(BaseModel):
    assessment: ModelReviewAssessment = ModelReviewAssessment.REVIEW_MANUALLY
    confidence: float = 0.0
    reason: str = ""
    blocking_factors: List[str] = Field(default_factory=list)
    recommended_actions: List[ModelReviewAction] = Field(default_factory=list)
    safe_to_promote: bool = False
    source: str = "openai"
    summary: Optional[ModelReviewSummary] = None


class ModelReviewComparison(BaseModel):
    workflow_id: str
    before_workflow_id: str
    after_workflow_id: str
    before: ModelReviewSummary
    after: ModelReviewSummary
    deltas: Dict[str, Any] = Field(default_factory=dict)
    applied_actions: List[ModelReviewAction] = Field(default_factory=list)
    accepted: bool = False


class ModelReviewProposalListResponse(BaseModel):
    workflow_id: str
    proposals: List[ModelReviewAction] = Field(default_factory=list)


class ModelReviewRerunRequest(BaseModel):
    proposal_ids: List[str] = Field(default_factory=list)


class DataProfileColumn(BaseModel):
    name: str
    inferred_type: str
    missing_rate: float = 0.0
    unique_ratio: float = 0.0
    low_variance: bool = False
    likely_identifier: bool = False
    warning_flags: List[str] = Field(default_factory=list)


class DataProfile(BaseModel):
    row_count: int = 0
    column_count: int = 0
    missing_rate_overall: float = 0.0
    columns: List[DataProfileColumn] = Field(default_factory=list)


class TargetFeasibility(BaseModel):
    target_column: Optional[str] = None
    target_kind: str = "unknown"
    feasibility: str = "unknown"
    baseline_metrics: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ModelSweepItem(BaseModel):
    algorithm: str
    status: str = "success"
    primary_metric: Optional[float] = None
    train_metric: Optional[float] = None
    test_metric: Optional[float] = None
    gap: Optional[float] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None


class ModelSweepResult(BaseModel):
    task_type: str = "unknown"
    items: List[ModelSweepItem] = Field(default_factory=list)
    best_algorithm: Optional[str] = None


class ExplorationNextAction(BaseModel):
    action: Literal[
        "inspect_features",
        "exclude_risky_columns",
        "change_target",
        "collect_more_rows",
        "try_balanced_class_weight",
        "try_regularized_model",
        "inspect_clusters",
        "inspect_outliers",
    ]
    reason: str
    priority: Literal["high", "medium", "low"] = "medium"


class ExplorationEvaluation(BaseModel):
    signal_strength: Literal["none", "weak", "medium", "strong", "unknown"] = "unknown"
    model_viability: Literal["not_useful", "unclear", "promising", "strong", "unknown"] = "unknown"
    overall_verdict: Literal["try_more", "usable_signal", "needs_better_features", "needs_better_target", "not_enough_data"] = "try_more"
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    next_actions: List[ExplorationNextAction] = Field(default_factory=list)


class ExplorationRequest(BaseModel):
    workbook_id: str
    sheet_name: str
    mapping: ColumnMapping = Field(default_factory=ColumnMapping)
    task_type: str = "auto"
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    split_mode: str = "ratio"
    test_size: float = 0.2
    train_size: Optional[float] = None
    random_state: int = 42
    shuffle: bool = True


class ExplorationResponse(BaseModel):
    workbook_id: str
    sheet_name: str
    data_profile: DataProfile
    target_feasibility: TargetFeasibility
    model_sweep: ModelSweepResult
    evaluation: ExplorationEvaluation


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
