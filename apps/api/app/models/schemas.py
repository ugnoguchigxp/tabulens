from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class ColumnInfo(BaseModel):
    name: str
    inferred_type: str
    missing_count: int

class SheetInfo(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]
    preview_rows: List[dict]

class WorkbookUploadResponse(BaseModel):
    workbook_id: str
    sheets: List[SheetInfo]

class WorkbookFormulaCell(BaseModel):
    address: str
    formula: str
    cached_value: Any = None


class WorkbookFormulaSheet(BaseModel):
    name: str
    cells: List[WorkbookFormulaCell] = Field(default_factory=list)


class WorkbookFormulaMetadataResponse(BaseModel):
    workbook_id: str
    sheets: List[WorkbookFormulaSheet] = Field(default_factory=list)


class SheetRowsResponse(BaseModel):
    workbook_id: str
    sheet_name: str
    offset: int
    limit: int
    row_count: int
    rows: List[dict] = Field(default_factory=list)


class SheetProfileResponse(BaseModel):
    workbook_id: str
    sheet_name: str
    row_count: int
    column_count: int
    missing_rate_overall: float

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

class WorkflowPredictRequest(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowPredictItem(BaseModel):
    value: Any = None
    confidence: Optional[float] = None


class WorkflowPredictResponse(BaseModel):
    workflow_id: str
    predictions: List[WorkflowPredictItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowRowsResponse(BaseModel):
    workflow_id: str
    rows: List[dict] = Field(default_factory=list)


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
    affected_columns: List[str] = Field(default_factory=list)


class ExplorationDecision(BaseModel):
    primary_message: str = ""
    recommended_path: Literal[
        "run_workflow",
        "adjust_features",
        "change_target",
        "collect_more_data",
        "inspect_data_quality",
        "use_baseline",
    ] = "adjust_features"
    primary_blocker: Optional[str] = None


class ExplorationEvaluation(BaseModel):
    signal_strength: Literal["none", "weak", "medium", "strong", "unknown"] = "unknown"
    model_viability: Literal["not_useful", "unclear", "promising", "strong", "unknown"] = "unknown"
    overall_verdict: Literal["try_more", "usable_signal", "needs_better_features", "needs_better_target", "not_enough_data"] = "try_more"
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    decision: ExplorationDecision = Field(default_factory=ExplorationDecision)
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
