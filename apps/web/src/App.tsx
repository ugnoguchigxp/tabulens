import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import { BarChart3, Settings2, Upload, Table as TableIcon, Plus, Trash2, Eraser, Columns, Rows, X, Wand2, Sparkles, Database, Filter, Gauge, ArrowDownNarrowWide, CheckSquare, Square, Maximize2 } from 'lucide-react'
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community'

ModuleRegistry.registerModules([AllCommunityModule])

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { BoundaryExplorer } from '@/components/boundary-explorer'
import { ReviewPanel } from '@/components/review-panel'
import {
  useUploadWorkbook,
  useRunAnalysis,
  useJobResults,
  useJobReviewSummary,
  useJobReviewResult,
  useJobProposals,
  useJobCompare,
  useJobBoundary,
  useReviewJob,
  useApplyProposal,
  useDiscardProposal,
} from '@/hooks/use-tabulens'

type WorkbookColumn = {
  name: string
  inferred_type: string
  missing_count: number
}

type WorkbookSheet = {
  name: string
  row_count: number
  columns: WorkbookColumn[]
  rows?: Array<Record<string, unknown>>
  preview_rows: Array<Record<string, unknown>>
}

type WorkbookUploadResponse = {
  workbook_id: string
  sheets: WorkbookSheet[]
}

type GridRow = Record<string, unknown>

interface ColumnMapping {
  feature_columns: string[]
  label_column: string
  id_column: string
}

interface ContextMenuState {
  x: number; y: number; visible: boolean; rowIndex: number | null; colId: string | null
}

const NUMERIC_TYPE_PATTERN = /(int|float|double|number|numeric|decimal|real)/i
const LABEL_HINT_PATTERN = /(^|_)(label|class|target|segment|group|category)(_|$)/i
const ID_HINT_PATTERN = /(^|_)(id|uuid|key)(_|$)/i

function isNumericColumn(column: WorkbookColumn) {
  return NUMERIC_TYPE_PATTERN.test(column.inferred_type)
}

function suggestMapping(sheet: WorkbookSheet): ColumnMapping {
  const columns = sheet.columns ?? []
  const idCandidate = columns.find((column) => ID_HINT_PATTERN.test(column.name))?.name ?? ''
  const categoricalColumns = columns.filter((column) => !isNumericColumn(column))
  const labelCandidate =
    columns.find((column) => LABEL_HINT_PATTERN.test(column.name))?.name ??
    (categoricalColumns.length === 1 ? categoricalColumns[0]?.name ?? '' : '')

  const feature_columns = columns
    .filter((column) => isNumericColumn(column))
    .map((column) => column.name)
    .filter((name) => name !== idCandidate && name !== labelCandidate)

  return {
    id_column: idCandidate,
    label_column: labelCandidate,
    feature_columns,
  }
}

function App() {
  const [selectedSheet, setSelectedSheet] = useState<number>(0)
  const [mapping, setMapping] = useState<ColumnMapping>({ feature_columns: [], label_column: '', id_column: '' })
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [jobMetadata, setJobMetadata] = useState<Record<string, unknown> | null>(null)
  const [showSettings, setShowSettings] = useState(true)
  const [showReviewPanel, setShowReviewPanel] = useState(true)
  const [showBoundaryModal, setShowBoundaryModal] = useState(false)
  const [showAnalysisDrawer, setShowAnalysisDrawer] = useState(false)
  const [localRowData, setLocalRowData] = useState<GridRow[]>([])
  const [extraColumns, setExtraColumns] = useState<string[]>([])
  const [proposalStatusById, setProposalStatusById] = useState<Record<string, 'applied' | 'discarded'>>({})
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ x: 0, y: 0, visible: false, rowIndex: null, colId: null })
  
  // Analysis Settings State
  const [analysisSettings, setAnalysisSettings] = useState({
    run_cleansing: true,
    run_feature_selection: true,
    run_ml: true,
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

  const fileInputRef = useRef<HTMLInputElement>(null)
  const gridRef = useRef<AgGridReact>(null)

  const uploadMutation = useUploadWorkbook()
  const analysisMutation = useRunAnalysis()
  const { data: resultRows, isLoading: resultsLoading } = useJobResults(activeJobId)
  const { data: reviewSummary } = useJobReviewSummary(activeJobId)
  const { data: reviewResult } = useJobReviewResult(activeJobId)
  const { data: proposals } = useJobProposals(activeJobId)
  const { data: comparison } = useJobCompare(activeJobId)
  const { data: boundary, isLoading: boundaryLoading, error: boundaryError } = useJobBoundary(activeJobId)
  const reviewMutation = useReviewJob(activeJobId)
  const applyProposalMutation = useApplyProposal(activeJobId)
  const discardProposalMutation = useDiscardProposal(activeJobId)

  const workbookData = uploadMutation.data as WorkbookUploadResponse | undefined
  const featureImportance = jobMetadata?.feature_importance as Record<string, number> | undefined
  const selectedFeatures = Array.isArray(jobMetadata?.selected_features) ? (jobMetadata.selected_features as string[]) : []
  const droppedFeatures = Array.isArray(jobMetadata?.dropped_features) ? (jobMetadata.dropped_features as string[]) : []
  const proposalItems = Array.isArray(proposals?.proposals) ? proposals.proposals : []
  const activeSheet = workbookData?.sheets[selectedSheet]
  const sourceRowCount = activeSheet?.row_count ?? 0
  const processedRowCount = resultRows?.length ?? 0
  const displayedRowCount = localRowData.length
  const suggestedMapping = activeSheet ? suggestMapping(activeSheet) : null
  const selectedLabelColumn = activeSheet?.columns.find((column) => column.name === mapping.label_column) ?? null
  const selectedLabelIsCategorical = selectedLabelColumn ? !isNumericColumn(selectedLabelColumn) : false
  const boundaryFeatureCount = mapping.feature_columns.filter((feature) => feature !== mapping.label_column).length
  const boundaryReady = !!mapping.label_column && selectedLabelIsCategorical && boundaryFeatureCount >= 2
  const allowDraftRowExtension = !resultRows

  useEffect(() => {
    setProposalStatusById({})
  }, [activeJobId])

  useEffect(() => {
    if (resultRows) setLocalRowData(resultRows)
    else if (workbookData) {
      const sheet = workbookData.sheets[selectedSheet]
      setLocalRowData(sheet.rows ?? sheet.preview_rows)
    }
  }, [resultRows, workbookData, selectedSheet])

  useEffect(() => {
    if (activeJobId) setShowReviewPanel(true)
  }, [activeJobId])

  useEffect(() => {
    if (!activeJobId) setShowBoundaryModal(false)
  }, [activeJobId])

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
          setActiveJobId(null); setJobMetadata(null); setSelectedSheet(0)
        }
      })
    }
  }

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
      run_ml: analysisSettings.run_ml
    }, {
      onSuccess: (data) => {
        setActiveJobId(data.job_id)
        setJobMetadata(data.metadata)
        setShowAnalysisDrawer(false)
        setShowReviewPanel(true)
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

  const handleApplyProposal = useCallback((proposalId: string) => {
    applyProposalMutation.mutate(proposalId, {
      onSuccess: (comparisonResult: any) => {
        const appliedProposals = Array.isArray(comparisonResult?.applied_proposals) ? comparisonResult.applied_proposals : []
        setProposalStatusById((current) => {
          const next = { ...current }
          if (appliedProposals.length > 0) {
            appliedProposals.forEach((proposal: any) => {
              if (proposal?.proposal_id) {
                next[String(proposal.proposal_id)] = 'applied'
              }
            })
          } else {
            next[proposalId] = 'applied'
          }
          return next
        })
      },
    })
  }, [applyProposalMutation])

  const handleDiscardProposal = useCallback((proposalId: string) => {
    discardProposalMutation.mutate(proposalId, {
      onSuccess: (proposal: any) => {
        if (!proposal?.proposal_id) return
        setProposalStatusById((current) => ({
          ...current,
          [String(proposal.proposal_id)]: 'discarded',
        }))
      },
    })
  }, [discardProposalMutation])

  const onCellContextMenu = useCallback((params: any) => {
    params.event.preventDefault(); params.event.stopPropagation();
    setContextMenu({ x: params.event.clientX, y: params.event.clientY, visible: true, rowIndex: params.node.rowIndex, colId: params.column.colId })
  }, [])

  const closeContextMenu = useCallback(() => setContextMenu(prev => ({ ...prev, visible: false })), [])
  useEffect(() => {
    window.addEventListener('click', closeContextMenu)
    return () => window.removeEventListener('click', closeContextMenu)
  }, [closeContextMenu])

  const handleInsertRow = (offset: number) => {
    if (contextMenu.rowIndex === null) return
    const newRow: GridRow = {}
    Object.keys(localRowData[0] ?? {}).forEach(k => {
      newRow[k] = null
    })
    const newData = [...localRowData]
    newData.splice(contextMenu.rowIndex + offset, 0, newRow)
    setLocalRowData(newData); closeContextMenu()
  }

  const handleDeleteRow = () => {
    if (contextMenu.rowIndex === null) return
    const newData = [...localRowData]; newData.splice(contextMenu.rowIndex, 1)
    setLocalRowData(newData); closeContextMenu()
  }

  const handleInsertColumn = () => {
    const colName = prompt("Enter column name:")
    if (colName) {
      setExtraColumns([...extraColumns, colName])
      setLocalRowData(localRowData.map(row => ({ ...row, [colName]: null })))
    }
    closeContextMenu()
  }

  const handleDeleteColumn = () => {
    if (!contextMenu.colId) return
    setLocalRowData(localRowData.map(row => { const nr = { ...row }; delete nr[contextMenu.colId!]; return nr }))
    setExtraColumns(extraColumns.filter(c => c !== contextMenu.colId)); closeContextMenu()
  }

  const columnKeys = useMemo(() => {
    if (localRowData.length > 0) {
      return Object.keys(localRowData[0])
    }
    return []
  }, [localRowData.length > 0 ? Object.keys(localRowData[0]).join(',') : ''])

  const columnDefs = useMemo(() => {
    const baseCols: any[] = [{
      headerName: "", valueGetter: (p: any) => p.node.rowIndex !== null ? p.node.rowIndex + 1 : null,
      width: 50, pinned: "left", cellStyle: { backgroundColor: "hsl(var(--muted))", textAlign: "center", fontSize: "10px", fontWeight: "bold" },
      suppressNavigable: true, sortable: false,
    }]
    
    if (columnKeys.length > 0) {
      baseCols.push(...columnKeys.map((key: string) => ({
        field: key, headerName: key, flex: 1, minWidth: 150,
        cellClass: (params: any) => {
          // Use params.colDef.field for better performance in cellClass
          const field = params.colDef.field;
          if (field.startsWith('norm_')) return 'bg-blue-50/30'
          if (field.startsWith('_')) return 'bg-green-50/50 font-semibold text-green-700'
          if (extraColumns.includes(field)) return 'bg-yellow-50/30'
          return ''
        }
      })))
    }
    return baseCols
  }, [columnKeys, extraColumns])

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
          <button className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs hover:bg-accent" onClick={() => { if (contextMenu.rowIndex !== null && contextMenu.colId) { const nd = [...localRowData]; nd[contextMenu.rowIndex][contextMenu.colId] = null; setLocalRowData(nd) }; closeContextMenu() }}><Eraser className="size-3" /> Clear Contents</button>
        </div>
      )}

      {/* Analysis Drawer */}
      {showAnalysisDrawer && (
        <div className="fixed inset-0 z-[110] flex justify-end bg-background/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-[450px] bg-background border-l shadow-2xl h-full flex flex-col animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 p-2 rounded-full"><Wand2 className="size-6 text-primary" /></div>
                <div>
                  <h2 className="text-xl font-bold">Analysis Engine</h2>
                  <p className="text-xs text-muted-foreground">Configure AI model & preprocessing</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setShowAnalysisDrawer(false)}><X className="size-5" /></Button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-8">
              {/* Data Cleansing Section */}
              <section className={cn("space-y-4 transition-opacity", !analysisSettings.run_cleansing && "opacity-50")}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    <Database className="size-4" /> 1. Data Cleansing
                  </div>
                  <button 
                    onClick={() => setAnalysisSettings({...analysisSettings, run_cleansing: !analysisSettings.run_cleansing})}
                    className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-primary hover:bg-primary/5 px-2 py-1 rounded"
                  >
                    {analysisSettings.run_cleansing ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                    {analysisSettings.run_cleansing ? "Enabled" : "Disabled"}
                  </button>
                </div>
                <Card className="border-slate-200 shadow-sm overflow-hidden">
                  <CardContent className="p-4 space-y-4">
                    <div className="space-y-2">
                      <Label className="text-xs">Handle Missing Values</Label>
                      <select 
                        disabled={!analysisSettings.run_cleansing}
                        value={analysisSettings.preprocessing.handle_missing}
                        onChange={e => setAnalysisSettings({...analysisSettings, preprocessing: {...analysisSettings.preprocessing, handle_missing: e.target.value}})}
                        className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs focus:ring-2 focus:ring-primary/20 transition-all disabled:opacity-50"
                      >
                        <option value="mean">Mean Imputation (Numeric)</option>
                        <option value="median">Median Imputation</option>
                        <option value="zero">Fill with Zero / Constant</option>
                        <option value="drop">Drop Rows with Missing Data</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-xs">Feature Scaling</Label>
                      <select 
                        disabled={!analysisSettings.run_cleansing}
                        value={analysisSettings.preprocessing.normalization}
                        onChange={e => setAnalysisSettings({...analysisSettings, preprocessing: {...analysisSettings.preprocessing, normalization: e.target.value}})}
                        className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs focus:ring-2 focus:ring-primary/20 transition-all disabled:opacity-50"
                      >
                        <option value="minmax">Min-Max Normalization (0-1)</option>
                        <option value="standard">Standard Scaling (Z-score)</option>
                        <option value="none">None (Raw Data)</option>
                      </select>
                    </div>
                  </CardContent>
                </Card>
              </section>

              {/* Feature Selection Section */}
              <section className={cn("space-y-4 transition-opacity", !analysisSettings.run_feature_selection && "opacity-50")}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    <Filter className="size-4" /> 2. Feature Selection (RF)
                  </div>
                  <button 
                    onClick={() => setAnalysisSettings({...analysisSettings, run_feature_selection: !analysisSettings.run_feature_selection})}
                    className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-primary hover:bg-primary/5 px-2 py-1 rounded"
                  >
                    {analysisSettings.run_feature_selection ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                    {analysisSettings.run_feature_selection ? "Enabled" : "Disabled"}
                  </button>
                </div>
                <Card className="border-slate-200 shadow-sm">
                  <CardContent className="p-4 space-y-4">
                    <div className="space-y-2">
                      <Label className="text-xs flex justify-between">
                        Importance Threshold 
                        <span className="text-primary font-bold">{(analysisSettings.preprocessing.feature_selection_threshold || 0).toFixed(2)}</span>
                      </Label>
                      <input 
                        disabled={!analysisSettings.run_feature_selection}
                        type="range" min="0" max="0.5" step="0.01"
                        value={analysisSettings.preprocessing.feature_selection_threshold || 0}
                        onChange={e => setAnalysisSettings({...analysisSettings, preprocessing: {...analysisSettings.preprocessing, feature_selection_threshold: parseFloat(e.target.value)}})}
                        className="w-full accent-primary disabled:opacity-50"
                      />
                      <p className="text-[10px] text-muted-foreground italic">Uses Random Forest by default to calculate importance.</p>
                    </div>
                  </CardContent>
                </Card>
              </section>

              {/* Algorithm Section */}
              <section className={cn("space-y-4 transition-opacity", !analysisSettings.run_ml && "opacity-50")}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    <Sparkles className="size-4" /> 3. ML Algorithm
                  </div>
                  <button 
                    onClick={() => setAnalysisSettings({...analysisSettings, run_ml: !analysisSettings.run_ml})}
                    className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-primary hover:bg-primary/5 px-2 py-1 rounded"
                  >
                    {analysisSettings.run_ml ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                    {analysisSettings.run_ml ? "Enabled" : "Disabled"}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: 'random_forest', name: 'Random Forest', type: 'Classification/Reg' },
                    { id: 'gradient_boosting', name: 'Gradient Boosting', type: 'Advanced' },
                    { id: 'svm', name: 'SVM', type: 'Kernel Based' },
                    { id: 'logistic_regression', name: 'Logistic Regression', type: 'Linear' },
                    { id: 'linear_regression', name: 'Linear Regression', type: 'Prediction' }
                  ].map(algo => (
                    <button
                      key={algo.id}
                      disabled={!analysisSettings.run_ml}
                      onClick={() => setAnalysisSettings({ ...analysisSettings, algorithm: algo.id })}
                      className={cn(
                        "flex flex-col items-start p-4 rounded-xl border-2 text-left transition-all disabled:opacity-50 disabled:hover:border-border",
                        analysisSettings.algorithm === algo.id 
                          ? "border-primary bg-primary/5 ring-4 ring-primary/10" 
                          : "border-border hover:border-primary/50"
                      )}
                    >
                      <span className="font-bold text-sm">{algo.name}</span>
                      <span className="text-[10px] opacity-60 mt-1">{algo.type}</span>
                    </button>
                  ))}
                </div>
              </section>
            </div>

            <div className="p-6 border-t bg-slate-50">
              <Button 
                className="w-full h-12 text-lg gap-3 shadow-lg" 
                onClick={handleRunAnalysis}
                disabled={analysisMutation.isPending || mapping.feature_columns.length === 0}
              >
                {analysisMutation.isPending ? 'Processing Pipeline...' : (
                  <>
                    <Sparkles className="size-5" />
                    Confirm & Start Pipeline
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
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
                setActiveJobId(null)
                setJobMetadata(null)
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
              {activeJobId && (
                <>
                  <Button
                    variant={showReviewPanel ? "secondary" : "ghost"}
                    size="sm"
                    className="h-9 gap-2 px-3"
                    onClick={() => setShowReviewPanel(!showReviewPanel)}
                  >
                    <BarChart3 className="size-4" />
                    <span className="hidden sm:inline">Review</span>
                  </Button>
                  <Button
                    variant={showBoundaryModal ? "secondary" : "ghost"}
                    size="sm"
                    className="h-9 gap-2 px-3"
                    onClick={() => setShowBoundaryModal(true)}
                  >
                    <Maximize2 className="size-4" />
                    <span className="hidden sm:inline">Graph</span>
                  </Button>
                </>
              )}
              <Button className="h-9 gap-2 px-4 ml-1 shadow-sm" onClick={() => setShowAnalysisDrawer(true)}>
                <Sparkles className="size-4" />
                <span className="hidden sm:inline">Analyze</span>
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
                  </div>
                  <div className="space-y-2 bg-white p-3 rounded-lg border shadow-sm">
                    {Object.entries(featureImportance)
                      .sort(([, a], [, b]) => (b as number) - (a as number))
                      .slice(0, 10)
                      .map(([name, score]) => (
                        <div key={name} className="space-y-1">
                          <div className="flex justify-between text-[10px] font-medium">
                            <span className="truncate max-w-[120px]">{name}</span>
                            <span>{((score as number) * 100).toFixed(1)}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-primary transition-all duration-1000" style={{ width: `${(score as number) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    {droppedFeatures.length > 0 && (
                      <div className="pt-2 border-t mt-2">
                        <Badge variant="secondary" className="text-[9px] h-4 py-0 flex items-center gap-1 w-fit bg-red-50 text-red-600 border-red-100">
                          <ArrowDownNarrowWide className="size-2.5" />
                          {droppedFeatures.length} features dropped
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
                    {workbookData.sheets[selectedSheet].columns.map((c: WorkbookColumn) => (<option key={c.name} value={c.name}>{c.name}</option>))}
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
                    {activeSheet?.columns.map((c: WorkbookColumn) => (
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
                        This will enable the boundary graph after rerunning analysis.
                      </p>
                    </div>
                  )}
                  <p className={cn(
                    "text-[10px] leading-4",
                    boundaryReady ? "text-emerald-700" : "text-muted-foreground"
                  )}>
                    {boundaryReady
                      ? "Boundary graph is shown below in this sidebar and in Review."
                      : selectedLabelColumn
                        ? (selectedLabelIsCategorical
                          ? "Choose at least two feature columns to show the boundary graph."
                          : `The selected label (${selectedLabelColumn.name}) is numeric. Pick a categorical label such as segment.`)
                        : "Choose a categorical label to enable the boundary graph."}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Features</Label>
                  <p className="text-[10px] text-muted-foreground">
                    Click chips to toggle features. The current label is excluded automatically.
                  </p>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {activeSheet?.columns.map((c: WorkbookColumn) => {
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

              {activeJobId && (
                <div className="space-y-3 pt-2 border-t border-slate-200">
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold flex items-center gap-2">
                      <BarChart3 className="size-4" />
                      Boundary Graph
                    </h3>
                    <p className="text-[10px] text-muted-foreground">
                      Open the decision boundary in a larger modal for inspection.
                    </p>
                  </div>
                  <Button className="w-full gap-2" variant="secondary" onClick={() => setShowBoundaryModal(true)}>
                    <Maximize2 className="size-4" />
                    Open Graph
                  </Button>
                </div>
              )}
            </div>
          </aside>
        )}

        <div className="flex flex-1 min-w-0 flex-col xl:flex-row overflow-hidden">
          <div className="flex flex-1 flex-col overflow-hidden">
            {!workbookData && !uploadMutation.isPending ? (
              <div className="flex flex-1 flex-col items-center justify-center bg-slate-50/50">
                <div className="rounded-full bg-white p-10 shadow-sm border mb-6 transition-transform hover:scale-105 duration-500"><TableIcon className="size-16 text-slate-200" /></div>
                <h2 className="text-xl font-semibold mb-2 text-slate-700 tracking-tight">No Workbook Loaded</h2>
                <p className="text-slate-400 mb-6 text-sm">Start by uploading an Excel or CSV file</p>
              </div>
            ) : (
              <div className="flex-1 ag-theme-quartz relative" onContextMenu={e => e.preventDefault()}>
                {resultsLoading && (<div className="absolute inset-0 z-50 flex items-center justify-center bg-background/50 backdrop-blur-sm"><Badge variant="secondary" className="animate-pulse py-2 px-4 text-sm gap-2 shadow-lg"><Sparkles className="size-4" /> Processing Pipeline...</Badge></div>)}
                <AgGridReact
                  ref={gridRef}
                  rowData={localRowData}
                  columnDefs={columnDefs}
                  pagination={true}
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

          {activeJobId && showReviewPanel && (
            <ReviewPanel
              jobId={activeJobId}
              reviewResult={reviewResult}
              reviewSummary={reviewSummary}
              proposals={proposalItems}
              proposalStatusById={proposalStatusById}
              comparison={comparison}
              boundary={boundary}
              boundaryLoading={boundaryLoading}
              boundaryError={boundaryError instanceof Error ? boundaryError.message : boundaryError ? String(boundaryError) : null}
              boundarySuggestedLabel={
                suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
                  ? suggestedMapping.label_column
                  : null
              }
              onUseBoundarySuggestedLabel={
                suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
                  ? handleUseSuggestedLabel
                  : undefined
              }
              onRefreshReview={() => reviewMutation.mutate()}
              onApplyProposal={handleApplyProposal}
              onDiscardProposal={handleDiscardProposal}
              isRefreshing={reviewMutation.isPending}
              isApplying={applyProposalMutation.isPending}
              isDiscarding={discardProposalMutation.isPending}
            />
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
            {selectedFeatures.length > 0 && (
              <span className="flex items-center gap-1 border-l pl-4 text-primary font-bold"><Filter className="size-3" />{selectedFeatures.length} Active Features</span>
            )}
          </div>
          <div className="flex items-center gap-2">
                <Badge variant="outline" className="h-4 px-1 text-[9px] tracking-wider uppercase font-bold bg-white">{activeJobId ? 'Pipeline Completed' : 'Ready'}</Badge>
                <span className="font-mono opacity-50">v1.3.0-ai</span>
              </div>
            </footer>
          )}

      {showBoundaryModal && activeJobId && (
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
                boundary={boundary ?? null}
                isLoading={boundaryLoading}
                errorMessage={boundaryError instanceof Error ? boundaryError.message : boundaryError ? String(boundaryError) : null}
                suggestedLabel={
                  suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
                    ? suggestedMapping.label_column
                    : null
                }
                onUseSuggestedLabel={
                  suggestedMapping && suggestedMapping.label_column && suggestedMapping.label_column !== mapping.label_column
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
