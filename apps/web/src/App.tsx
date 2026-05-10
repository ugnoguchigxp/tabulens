import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import { BarChart3, Settings2, Upload, Table as TableIcon, Plus, Trash2, Eraser, Columns, Rows, X, Sparkles, Database, Gauge, ArrowDownNarrowWide, Maximize2, Play, Search } from 'lucide-react'
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community'

ModuleRegistry.registerModules([AllCommunityModule])

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'
import { BoundaryExplorer } from '@/components/boundary-explorer'
import { WorkflowDrawer } from '@/components/workflow-drawer'
import { WorkflowPanel } from '@/components/workflow-panel'
import { ExplorationPanel } from '@/components/exploration-panel'
import {
  useUploadWorkbook,
  useRunAnalysis,
  useRunModelWorkflow,
  useRunExploration,
  useJobResults,
  useJobBoundary,
  useWorkflowBoundary,
} from '@/hooks/use-tabulens'
import { useGridEditor } from '@/hooks/use-grid-editor'
import { PrepareDrawer } from '@/components/prepare-drawer'

import {
  isNumericColumn,
  suggestMapping,
  inferColumnsFromRows,
  createDefaultWorkflowSettings
} from '@/lib/workbook-utils'
import type {
  WorkbookColumn,
  WorkbookSheet,
  ColumnMapping,
  WorkflowSettings
} from '@/lib/workbook-utils'
type WorkbookUploadResponse = {
  workbook_id: string
  sheets: WorkbookSheet[]
}

type GridRow = Record<string, unknown>
const LOW_IMPORTANCE_THRESHOLD = 0.2

function App() {
  const [selectedSheet, setSelectedSheet] = useState<number>(0)
  const [mapping, setMapping] = useState<ColumnMapping>({ feature_columns: [], label_column: '', id_column: '' })
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null)
  const [jobMetadata, setJobMetadata] = useState<Record<string, unknown> | null>(null)
  const [workflowResult, setWorkflowResult] = useState<any | null>(null)
  const [showSettings, setShowSettings] = useState(true)
  const [showWorkflowPanel, setShowWorkflowPanel] = useState(true)
  const [showWorkflowDrawer, setShowWorkflowDrawer] = useState(false)
  const [showBoundaryModal, setShowBoundaryModal] = useState(false)
  const [showAnalysisDrawer, setShowAnalysisDrawer] = useState(false)
  const [explorationResult, setExplorationResult] = useState<any | null>(null)
  const [manuallyDroppedFeatures, setManuallyDroppedFeatures] = useState<string[]>([])
  const [sheetPage, setSheetPage] = useState(0)

  const {
    localRowData,
    setLocalRowData,
    extraColumns,
    contextMenu,
    setContextMenu,
    closeContextMenu,
    handleInsertRow,
    handleDeleteRow,
    handleInsertColumn,
    handleDeleteColumn,
    removeColumn,
    handleClearCell,
    columnKeys,
  } = useGridEditor([])
  
  // Analysis Settings State
  const [analysisSettings, setAnalysisSettings] = useState({
    run_cleansing: true,
    run_feature_selection: true,
    algorithm: 'random_forest',
    preprocessing: {
      handle_missing: 'mean',
      normalization: 'minmax',
      outlier_removal: false,
      categorical_encoding: 'label',
      calculate_importance: true,
      feature_selection_threshold: 0.01
    }
  })
  const [workflowSettings, setWorkflowSettings] = useState<WorkflowSettings>(() => createDefaultWorkflowSettings())

  const fileInputRef = useRef<HTMLInputElement>(null)
  const gridRef = useRef<AgGridReact>(null)

  const uploadMutation = useUploadWorkbook()
  const analysisMutation = useRunAnalysis()
  const workflowMutation = useRunModelWorkflow()
  const explorationMutation = useRunExploration()
  const { data: resultRows, isLoading: resultsLoading } = useJobResults(activeJobId)
  const { data: boundary, isLoading: boundaryLoading, error: boundaryError } = useJobBoundary(activeJobId)
  const {
    data: workflowBoundary,
    isLoading: workflowBoundaryLoading,
    error: workflowBoundaryError,
  } = useWorkflowBoundary(activeWorkflowId, !!activeWorkflowId && workflowResult?.use_case === 'classification')

  const workbookData = uploadMutation.data as WorkbookUploadResponse | undefined
  const featureImportance = jobMetadata?.feature_importance as Record<string, number> | undefined
  const allDroppedFeatures = useMemo(() => manuallyDroppedFeatures, [manuallyDroppedFeatures])
  const activeSheet = workbookData?.sheets[selectedSheet]
  const visibleSheetColumns = useMemo(
    () => (activeSheet?.columns ?? []).filter((column) => !manuallyDroppedFeatures.includes(column.name)),
    [activeSheet, manuallyDroppedFeatures]
  )
  const sourceRowCount = activeSheet?.row_count ?? 0
  const processedRowCount = activeWorkflowId
    ? Array.isArray(workflowResult?.rows)
      ? workflowResult.rows.length
      : 0
    : resultRows?.length ?? 0
  const displayedRowCount = localRowData.length
  const suggestedMapping = activeSheet ? suggestMapping(activeSheet) : null
  const selectedLabelColumn = activeSheet?.columns.find((column) => column.name === mapping.label_column) ?? null
  const selectedLabelIsCategorical = selectedLabelColumn ? !isNumericColumn(selectedLabelColumn) : false
  const boundaryFeatureCount = mapping.feature_columns.filter((feature) => feature !== mapping.label_column).length
  const boundaryReady = !!mapping.label_column && selectedLabelIsCategorical && boundaryFeatureCount >= 2
  const workflowBoundaryReady = !!activeWorkflowId && workflowResult?.use_case === 'classification'
  const workbookPreviewMode = !!workbookData && !activeJobId && !activeWorkflowId
  const allowDraftRowExtension = !resultRows && !activeWorkflowId
  const isProcessing = resultsLoading || analysisMutation.isPending || workflowMutation.isPending || explorationMutation.isPending
  const preparedSourceColumns = activeJobId ? inferColumnsFromRows(localRowData) : undefined
  const preparedSourceRowCount = activeJobId ? localRowData.length : undefined
  const activeBoundary = workflowBoundaryReady ? workflowBoundary : boundary
  const activeBoundaryLoading = workflowBoundaryReady ? workflowBoundaryLoading : boundaryLoading
  const activeBoundaryError = workflowBoundaryReady ? workflowBoundaryError : boundaryError
  const totalWorkbookPages = Math.max(1, Math.ceil(sourceRowCount / 100))

  useEffect(() => {
    if (resultRows) {
      setLocalRowData(resultRows)
      return
    }
    if (activeWorkflowId && Array.isArray(workflowResult?.rows)) {
      setLocalRowData(workflowResult.rows)
      return
    }
    if (!workbookData) {
      return
    }

    const sheet = workbookData.sheets[selectedSheet]
    setLocalRowData(sheet.preview_rows ?? [])

    let isCancelled = false
    const offset = sheetPage * 100
    void apiClient
      .getWorkbookRows(workbookData.workbook_id, sheet.name, offset, 100)
      .then((response) => {
        if (isCancelled) return
        if (Array.isArray(response?.rows)) {
          setLocalRowData(response.rows)
        }
      })
      .catch(() => {
        // keep preview rows when paged fetch fails
      })

    return () => {
      isCancelled = true
    }
  }, [resultRows, activeWorkflowId, workflowResult, workbookData, selectedSheet, sheetPage, setLocalRowData])

  useEffect(() => {
    if (!activeJobId && !workflowBoundaryReady) setShowBoundaryModal(false)
  }, [activeJobId, workflowBoundaryReady])

  useEffect(() => {
    if (!showBoundaryModal) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowBoundaryModal(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [showBoundaryModal])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      uploadMutation.mutate(e.target.files[0], {
        onSuccess: (data) => {
          const sheet = data.sheets[0]
          setMapping(suggestMapping(sheet))
          setActiveJobId(null)
          setActiveWorkflowId(null)
          setJobMetadata(null)
          setWorkflowResult(null)
          setExplorationResult(null)
          setManuallyDroppedFeatures([])
          setSelectedSheet(0)
          setShowWorkflowPanel(true)
        }
      })
    }
  }

  const handleDropLowImportanceFeature = useCallback((featureName: string) => {
    const isDroppable =
      mapping.feature_columns.includes(featureName) &&
      mapping.label_column !== featureName &&
      mapping.id_column !== featureName
    if (!isDroppable) return

    removeColumn(featureName)
    setMapping((current) => ({
      ...current,
      feature_columns: current.feature_columns.filter((feature) => feature !== featureName),
    }))
    setManuallyDroppedFeatures((current) => (current.includes(featureName) ? current : [...current, featureName]))
  }, [mapping.feature_columns, mapping.id_column, mapping.label_column, removeColumn])

  const submitAnalysis = async (mappingToUse: ColumnMapping) => {
    if (!workbookData) return
    analysisMutation.mutate({
      workbook_id: workbookData.workbook_id,
      sheet_name: workbookData.sheets[selectedSheet].name,
      mapping: mappingToUse,
      algorithm: analysisSettings.algorithm as any,
      preprocessing: analysisSettings.preprocessing,
      run_cleansing: analysisSettings.run_cleansing,
      run_feature_selection: analysisSettings.run_feature_selection,
      run_ml: false
    }, {
      onSuccess: (data) => {
        setActiveJobId(data.job_id)
        setActiveWorkflowId(null)
        setWorkflowResult(null)
        setExplorationResult(null)
        setJobMetadata(data.metadata)
        setShowAnalysisDrawer(false)
        setShowWorkflowPanel(false)
      }
    })
  }

  const handleRunAnalysis = async () => {
    await submitAnalysis(mapping)
  }

  const handleUseSuggestedLabel = async () => {
    if (!suggestedMapping?.label_column) return
    const nextMapping: ColumnMapping = {
      ...suggestedMapping,
      id_column: suggestedMapping.id_column || mapping.id_column,
    }
    setMapping(nextMapping)
    await submitAnalysis(nextMapping)
  }

  const submitWorkflow = async () => {
    if (!workbookData || !activeSheet || !activeJobId) return

    const nextMapping: ColumnMapping = {
      ...mapping,
      feature_columns: mapping.feature_columns.filter((feature) => feature !== mapping.label_column),
    }

    workflowMutation.mutate({
      workbook_id: workbookData.workbook_id,
      sheet_name: activeSheet.name,
      source_job_id: activeJobId,
      use_case: workflowSettings.use_case,
      mapping: nextMapping,
      algorithm: workflowSettings.algorithm,
      params: workflowSettings.params,
    }, {
      onSuccess: (data) => {
        setActiveWorkflowId(data.workflow_id)
        setWorkflowResult(data)
        setActiveJobId(null)
        setJobMetadata(null)
        setShowWorkflowDrawer(false)
        setShowWorkflowPanel(true)
        setExplorationResult(null)
        if (Array.isArray(data.rows)) {
          setLocalRowData(data.rows)
        }
      },
    })
  }

  const runExploration = useCallback(() => {
    if (!workbookData || !activeSheet) return
    const selectedLabel = activeSheet.columns.find((column) => column.name === mapping.label_column) ?? null
    const inferredTaskType = !selectedLabel
      ? 'auto'
      : isNumericColumn(selectedLabel)
        ? 'regression'
        : 'classification'
    explorationMutation.mutate(
      {
        workbook_id: workbookData.workbook_id,
        sheet_name: activeSheet.name,
        mapping,
        task_type: inferredTaskType,
        preprocessing: analysisSettings.preprocessing,
      },
      {
        onSuccess: (data) => {
          setExplorationResult(data)
          setShowWorkflowPanel(false)
        },
      }
    )
  }, [workbookData, activeSheet, mapping, explorationMutation, analysisSettings.preprocessing])


  const onCellContextMenu = useCallback((params: any) => {
    params.event.preventDefault(); params.event.stopPropagation();
    setContextMenu({ x: params.event.clientX, y: params.event.clientY, visible: true, rowIndex: params.node.rowIndex, colId: params.column.colId })
  }, [setContextMenu])

  const closeContextMenuAndExtra = useCallback(() => closeContextMenu(), [closeContextMenu])
  useEffect(() => {
    window.addEventListener('click', closeContextMenuAndExtra)
    return () => window.removeEventListener('click', closeContextMenuAndExtra)
  }, [closeContextMenuAndExtra])


  const columnKeysList = columnKeys;

  const columnDefs = useMemo(() => {
    const baseCols: any[] = [{
      headerName: "", valueGetter: (p: any) => p.node.rowIndex !== null ? p.node.rowIndex + 1 : null,
      width: 50, pinned: "left", cellStyle: { backgroundColor: "hsl(var(--muted))", textAlign: "center", fontSize: "10px", fontWeight: "bold" },
      suppressNavigable: true, sortable: false,
    }]
    
    if (columnKeysList.length > 0) {
      baseCols.push(...columnKeysList.map((key: string) => ({
        field: key, headerName: key, flex: 1, minWidth: 150,
        cellClass: (params: any) => {
          const field = params.colDef.field;
          if (field.startsWith('norm_')) return 'bg-blue-50/30'
          if (field.startsWith('_')) return 'bg-green-50/50 font-semibold text-green-700'
          if (extraColumns.includes(field)) return 'bg-yellow-50/30'
          return ''
        }
      })))
    }
    return baseCols
  }, [columnKeysList, extraColumns])

  return (
    <div className="flex h-screen flex-col bg-background overflow-hidden relative">
      {/* Context Menu */}
      {contextMenu.visible && (
        <div className="fixed z-[100] w-56 rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in zoom-in-95" style={{ top: contextMenu.y, left: contextMenu.x }}>
          <div className="px-2 py-1.5 text-[10px] font-semibold text-muted-foreground border-b mb-1 uppercase tracking-wider">Cell Actions</div>
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-accent" onClick={() => handleInsertRow(0)}><Rows className="size-3" /> Insert Row Above</button>
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-accent" onClick={() => handleInsertRow(1)}><Plus className="size-3" /> Insert Row Below</button>
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10" onClick={handleDeleteRow}><Trash2 className="size-3" /> Delete Row</button>
          <div className="my-1 h-px bg-border" />
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-accent" onClick={handleInsertColumn}><Columns className="size-3" /> Insert Column</button>
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10" onClick={handleDeleteColumn}><Trash2 className="size-3" /> Delete Column</button>
          <div className="my-1 h-px bg-border" />
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-accent" onClick={handleClearCell}><Eraser className="size-3" /> Clear Contents</button>
        </div>
      )}

      {/* Prepare Drawer */}
      {showAnalysisDrawer && (
        <PrepareDrawer
          settings={analysisSettings}
          setSettings={setAnalysisSettings}
          onClose={() => setShowAnalysisDrawer(false)}
          onRun={handleRunAnalysis}
          isPending={analysisMutation.isPending}
          canRun={mapping.feature_columns.length > 0}
        />
      )}

      {showWorkflowDrawer && workbookData && (
            <WorkflowDrawer
              workbookData={workbookData}
              selectedSheet={selectedSheet}
              sourceColumns={preparedSourceColumns}
              sourceRowCount={preparedSourceRowCount}
              sourceLabel={activeJobId ? 'Prepared Dataset' : undefined}
              mapping={mapping}
          setMapping={setMapping}
          workflowSettings={workflowSettings}
          setWorkflowSettings={setWorkflowSettings}
          onClose={() => setShowWorkflowDrawer(false)}
          onRun={submitWorkflow}
          isRunning={workflowMutation.isPending}
        />
      )}

      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-4 bg-background z-50 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 mr-4">
            <div className="rounded-lg bg-primary p-1 text-primary-foreground"><BarChart3 className="size-5" /></div>
            <span className="text-lg font-bold tracking-tight text-primary">TabuLens</span>
          </div>
          {workbookData && (
            <div className="flex items-center gap-2 border-l pl-4 h-8">
              <select value={selectedSheet} onChange={(e) => {
                const nextSheet = Number(e.target.value)
                setSelectedSheet(nextSheet)
                setSheetPage(0)
                setActiveJobId(null)
                setActiveWorkflowId(null)
                setJobMetadata(null)
                setWorkflowResult(null)
                setExplorationResult(null)
                setManuallyDroppedFeatures([])
                if (workbookData?.sheets[nextSheet]) {
                  setMapping(suggestMapping(workbookData.sheets[nextSheet]))
                }
              }} className="h-8 rounded-md border bg-background px-2 text-xs font-medium">
                {workbookData.sheets.map((s: WorkbookSheet, i: number) => (<option key={i} value={i}>{s.name}</option>))}
              </select>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".xlsx,.csv" className="hidden" />
          <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => fileInputRef.current?.click()}><Upload className={cn("size-5", uploadMutation.isPending && "animate-bounce text-primary")} /></Button>
          {workbookData && (
            <>
              <Button variant={showSettings ? "secondary" : "ghost"} size="icon" className="h-9 w-9" onClick={() => setShowSettings(!showSettings)}><Settings2 className="size-5" /></Button>
              {activeWorkflowId && (
                <>
                  <Button
                    variant={showWorkflowPanel ? "secondary" : "ghost"}
                    size="sm"
                    className="h-9 gap-2 px-3"
                    onClick={() => setShowWorkflowPanel(!showWorkflowPanel)}
                  >
                    <Database className="size-4" />
                    <span className="hidden sm:inline">Workflow</span>
                  </Button>
                  {workflowBoundaryReady && (
                    <Button
                      variant={showBoundaryModal ? "secondary" : "ghost"}
                      size="sm"
                      className="h-9 gap-2 px-3"
                      onClick={() => setShowBoundaryModal(true)}
                    >
                      <Maximize2 className="size-4" />
                      <span className="hidden sm:inline">Graph</span>
                    </Button>
                  )}
                </>
              )}
              <Button
                className="h-9 gap-2 px-4 ml-1 shadow-sm"
                onClick={() => {
                  setShowWorkflowDrawer(false)
                  setShowAnalysisDrawer(true)
                }}
              >
                <Sparkles className="size-4" />
                <span className="hidden sm:inline">Prepare</span>
              </Button>
              <Button
                variant="secondary"
                className="h-9 gap-2 px-4 shadow-sm"
                onClick={runExploration}
                disabled={mapping.feature_columns.length === 0 || explorationMutation.isPending}
                title={mapping.feature_columns.length === 0 ? 'Select feature columns before exploration' : 'Run Exploration'}
              >
                <Search className="size-4" />
                <span className="hidden sm:inline">{explorationMutation.isPending ? 'Exploring...' : 'Explore'}</span>
              </Button>
              <Button
                variant="secondary"
                className="h-9 gap-2 px-4 shadow-sm"
                disabled={!activeJobId}
                title={!activeJobId ? 'Run Prepare before Workflow' : 'Open Workflow'}
                onClick={() => {
                  if (!activeJobId) return
                  setShowAnalysisDrawer(false)
                  setShowWorkflowDrawer(true)
                }}
              >
                <Play className="size-4" />
                <span className="hidden sm:inline">Workflow</span>
              </Button>
            </>
          )}
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        {workbookData && showSettings && (
          <aside className="w-80 shrink-0 border-r bg-slate-50/30 overflow-y-auto animate-in slide-in-from-left duration-200">
            <div className="p-4 space-y-6">
              {/* Feature Importance Insight */}
              {featureImportance && (
                <div className="space-y-4 animate-in fade-in zoom-in-95 duration-500">
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold flex items-center gap-2 text-primary uppercase tracking-tighter"><Gauge className="size-3" /> Feature Insights</h3>
                    <p className="text-[10px] text-muted-foreground">Relative importance scores</p>
                    <p className="text-[10px] text-muted-foreground">Features at or below 20% can be dropped from current analysis.</p>
                  </div>
                  <div className="space-y-2 bg-white p-3 rounded-lg border shadow-sm">
                    {Object.entries(featureImportance)
                      .sort(([, a], [, b]) => (b as number) - (a as number))
                      .map(([name, score]) => {
                        const normalizedScore = Number(score)
                        const canDrop = normalizedScore <= LOW_IMPORTANCE_THRESHOLD
                        const isDropped = manuallyDroppedFeatures.includes(name)
                        const isSelectedFeature = mapping.feature_columns.includes(name)
                        return (
                          <div key={name} className="space-y-1">
                            <div className="flex justify-between text-[10px] font-medium">
                              <span className="truncate max-w-[120px]">{name}</span>
                              <span>{(normalizedScore * 100).toFixed(1)}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full bg-primary transition-all duration-1000" style={{ width: `${normalizedScore * 100}%` }} />
                            </div>
                            {canDrop && (
                              <div className="flex justify-end">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-6 px-2 text-[10px]"
                                  onClick={() => handleDropLowImportanceFeature(name)}
                                  disabled={isDropped || !isSelectedFeature}
                                >
                                  <Trash2 className="mr-1 size-3" />
                                  {isDropped ? 'Dropped' : 'Drop column'}
                                </Button>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    {allDroppedFeatures.length > 0 && (
                      <div className="pt-2 border-t mt-2">
                        <Badge variant="secondary" className="text-[9px] h-4 py-0 flex items-center gap-1 w-fit bg-red-50 text-red-600 border-red-100">
                          <ArrowDownNarrowWide className="size-2.5" />
                          {allDroppedFeatures.length} features dropped
                        </Badge>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="space-y-1 pt-2 border-t border-slate-200">
                <h3 className="text-sm font-semibold flex items-center gap-2"><Settings2 className="size-4" /> Mapping Settings</h3>
              </div>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-xs">ID Column</Label>
                  <select value={mapping.id_column} onChange={e => setMapping({...mapping, id_column: e.target.value})} className="w-full h-9 rounded-md border bg-background px-2 text-xs">
                    <option value="">None</option>
                    {visibleSheetColumns.map((c: WorkbookColumn) => (<option key={c.name} value={c.name}>{c.name}</option>))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Label Column</Label>
                  <select
                    value={mapping.label_column}
                    onChange={(e) => {
                      const nextLabel = e.target.value
                      setMapping((current) => ({
                        ...current,
                        label_column: nextLabel,
                        feature_columns: current.feature_columns.filter((feature) => feature !== nextLabel),
                      }))
                    }}
                    className="w-full h-9 rounded-md border bg-background px-2 text-xs"
                  >
                    <option value="">None (Unsupervised)</option>
                    {visibleSheetColumns.map((c: WorkbookColumn) => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                  {suggestedMapping?.label_column && suggestedMapping.label_column !== mapping.label_column && (
                    <div className="rounded-md border border-amber-200 bg-amber-50/80 px-3 py-2 text-[10px] leading-4 text-amber-900">
                      <div className="flex items-center justify-between gap-2">
                        <span>
                          Suggested label: <span className="font-semibold">{suggestedMapping.label_column}</span>
                        </span>
                        <button
                          className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold text-amber-900 hover:bg-amber-100"
                          onClick={() => {
                            const nextMapping: ColumnMapping = {
                              ...suggestedMapping,
                              id_column: suggestedMapping.id_column || mapping.id_column,
                            }
                            setMapping(nextMapping)
                          }}
                        >
                          Use
                        </button>
                      </div>
                      <p className="mt-1 text-[10px] text-amber-700">
                        This will update the prepared feature set before workflow training.
                      </p>
                    </div>
                  )}
                  <p className={cn(
                    "text-[10px] leading-4",
                    boundaryReady ? "text-emerald-700" : "text-muted-foreground"
                  )}>
                    {boundaryReady
                      ? "Classification Workflow の完了後に Graph ボタンから境界グラフを表示できます。"
                      : selectedLabelColumn
                        ? (selectedLabelIsCategorical
                          ? "境界グラフには2つ以上の特徴量が必要です。"
                          : `The selected label (${selectedLabelColumn.name}) is numeric. Pick a categorical label such as segment.`)
                        : "分類境界グラフにはカテゴリ型の Label が必要です。"}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Features</Label>
                  <p className="text-[10px] text-muted-foreground">
                    Click chips to toggle features. The current label is excluded automatically.
                  </p>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {visibleSheetColumns.map((c: WorkbookColumn) => {
                      const isSelected = mapping.feature_columns.includes(c.name)
                      const isLabel = mapping.label_column === c.name
                      return (
                        <button
                          key={c.name}
                          disabled={isLabel}
                          onClick={() => {
                            const next = isSelected
                              ? mapping.feature_columns.filter((feature) => feature !== c.name)
                              : [...mapping.feature_columns, c.name]
                            setMapping({ ...mapping, feature_columns: next })
                          }}
                          className={cn(
                            "inline-flex items-center rounded-md border px-2 py-1 text-[10px] font-medium transition-all",
                            isLabel && "cursor-not-allowed border-amber-300 bg-amber-50 text-amber-800",
                            !isLabel && isSelected
                              ? "bg-primary text-primary-foreground border-primary shadow-sm"
                              : !isLabel && "bg-background border-slate-200 hover:border-primary/30",
                          )}
                          title={isLabel ? "Label column is excluded from features" : c.name}
                        >
                          {c.name}
                          {isLabel && <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wide">label</span>}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>

            </div>
          </aside>
        )}

        <div className="flex flex-1 min-w-0 flex-col xl:flex-row overflow-hidden">
          <div className="flex flex-1 flex-col overflow-hidden">
            {!workbookData && !uploadMutation.isPending ? (
              <div className="flex flex-1 flex-col items-center justify-center bg-slate-50/50">
                <div className="rounded-full bg-white p-10 shadow-sm border mb-6 transition-transform hover:scale-105 duration-500"><TableIcon className="size-16 text-slate-200" /></div>
                <h2 className="text-xl font-semibold mb-2 text-slate-700 tracking-tight">Local ML Feasibility Check</h2>
                <p className="text-slate-400 mb-6 text-sm">Upload a local workbook to check whether it contains usable ML signal.</p>
              </div>
            ) : (
              <div className="flex-1 ag-theme-quartz relative" onContextMenu={e => e.preventDefault()}>
                {isProcessing && (<div className="absolute inset-0 z-50 flex items-center justify-center bg-background/50 backdrop-blur-sm"><Badge variant="secondary" className="animate-pulse py-2 px-4 text-sm gap-2 shadow-lg"><Sparkles className="size-4" /> Processing...</Badge></div>)}
                <AgGridReact
                  ref={gridRef}
                  rowData={localRowData}
                  columnDefs={columnDefs}
                  pagination={!workbookPreviewMode}
                  paginationPageSize={100}
                  // Virtualization & Performance
                  rowBuffer={20}
                  debounceVerticalScrollbar={true}
                  suppressColumnVirtualisation={false}
                  rowModelType="clientSide"
                  animateRows={false} // Performance: set to false for very large datasets
                  suppressScrollOnNewData={true}
                  
                  onCellContextMenu={onCellContextMenu}
                  enterNavigatesVerticallyAfterEdit={true}
                  onCellFocused={(p) => {
                    if (!allowDraftRowExtension) {
                      return
                    }
                    // Optimized: only add row if focusing the last row AND the last row isn't already empty
                    if (p.rowIndex !== null && p.rowIndex === localRowData.length - 1) {
                      const lastRow = localRowData[localRowData.length - 1];
                      const isLastRowEmpty = Object.values(lastRow).every(v => v === null || v === "");
                      
                      if (!isLastRowEmpty) {
                        const nr: GridRow = {}
                        Object.keys(localRowData[0] ?? {}).forEach(c => {
                          nr[c] = null
                        })
                        setLocalRowData(prev => [...prev, nr])
                      }
                    }
                  }}
                  defaultColDef={{ 
                    editable: true, 
                    sortable: true, 
                    filter: true, 
                    resizable: true, 
                    valueFormatter: (p) => p.value == null ? "" : String(p.value),
                    suppressMovable: false,
                  }}
                />
              </div>
            )}
          </div>

          {activeWorkflowId && showWorkflowPanel && (
            <WorkflowPanel
              workflowId={activeWorkflowId}
              useCase={workflowResult?.use_case ?? workflowSettings.use_case}
              result={workflowResult}
            />
          )}

          {!activeJobId && !activeWorkflowId && explorationResult && (
            <ExplorationPanel result={explorationResult} />
          )}
        </div>
      </main>

      {workbookData && (
        <footer className="flex h-8 shrink-0 items-center justify-between border-t px-4 bg-slate-50 text-[10px] text-muted-foreground z-50">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1 font-medium"><TableIcon className="size-3" />{workbookData.sheets[selectedSheet].name}</span>
            <span className="flex items-center gap-1 border-l pl-4 font-mono">
              Source {sourceRowCount} Rows
            </span>
            <span className="flex items-center gap-1 border-l pl-4 font-mono">
              {processedRowCount > 0 ? `Processed ${processedRowCount} Rows` : `Displayed ${displayedRowCount} Rows`}
            </span>
            <span className="flex items-center gap-1 border-l pl-4 font-mono">
              Visible {displayedRowCount} Rows
            </span>
            {explorationResult && (
              <span className="flex items-center gap-1 border-l pl-4 text-emerald-700 font-semibold">
                <Search className="size-3" />
                Exploration Ready
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {workbookPreviewMode && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => setSheetPage((current) => Math.max(0, current - 1))}
                  disabled={sheetPage <= 0}
                >
                  Prev
                </Button>
                <span className="font-mono text-[10px]">
                  Page {sheetPage + 1}/{totalWorkbookPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => setSheetPage((current) => Math.min(totalWorkbookPages - 1, current + 1))}
                  disabled={sheetPage >= totalWorkbookPages - 1}
                >
                  Next
                </Button>
              </>
            )}
            <Badge variant="outline" className="h-4 px-1 text-[9px] tracking-wider uppercase font-bold bg-white">
              {activeJobId ? 'Prepare Completed' : activeWorkflowId ? 'Workflow Completed' : explorationResult ? 'Explored' : 'Ready'}
            </Badge>
            <span className="font-mono opacity-50">v1.3.0-ai</span>
          </div>
        </footer>
      )}

      {showBoundaryModal && (activeJobId || workflowBoundaryReady) && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/60 px-3 py-4 backdrop-blur-sm"
          onClick={() => setShowBoundaryModal(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Boundary graph modal"
        >
          <div
            className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 border-b bg-slate-50 px-4 py-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Boundary Graph</p>
                <h3 className="text-base font-bold text-foreground">Decision Surface</h3>
              </div>
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => setShowBoundaryModal(false)}>
                <X className="size-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <BoundaryExplorer
                boundary={activeBoundary ?? null}
                isLoading={activeBoundaryLoading}
                errorMessage={activeBoundaryError instanceof Error ? activeBoundaryError.message : activeBoundaryError ? String(activeBoundaryError) : null}
                suggestedLabel={
                  !workflowBoundaryReady && suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
                    ? suggestedMapping.label_column
                    : null
                }
                onUseSuggestedLabel={
                  !workflowBoundaryReady && suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
                    ? handleUseSuggestedLabel
                    : undefined
                }
              />
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

export default App
