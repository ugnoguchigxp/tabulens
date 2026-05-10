import { X, Wand2, Database, CheckSquare, Square, Filter, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface PrepareSettings {
  run_cleansing: boolean
  run_feature_selection: boolean
  algorithm: string
  preprocessing: {
    handle_missing: string
    normalization: string
    outlier_removal: boolean
    categorical_encoding: string
    calculate_importance: boolean
    feature_selection_threshold: number
  }
}

interface PrepareDrawerProps {
  settings: PrepareSettings
  setSettings: (settings: PrepareSettings) => void
  onClose: () => void
  onRun: () => void
  isPending: boolean
  canRun: boolean
}

export function PrepareDrawer({
  settings,
  setSettings,
  onClose,
  onRun,
  isPending,
  canRun
}: PrepareDrawerProps) {
  return (
    <div className="fixed inset-0 z-[110] flex justify-end bg-background/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[450px] bg-background border-l shadow-2xl h-full flex flex-col animate-in slide-in-from-right duration-300">
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="bg-primary/10 p-2 rounded-full"><Wand2 className="size-6 text-primary" /></div>
            <div>
              <h2 className="text-xl font-bold">Prepare Dataset</h2>
              <p className="text-xs text-muted-foreground">Clean data and optimize columns before training</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="size-5" /></Button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* Data Cleansing Section */}
          <section className={cn("space-y-4 transition-opacity", !settings.run_cleansing && "opacity-50")}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                <Database className="size-4" /> 1. Data Cleansing
              </div>
              <button 
                onClick={() => setSettings({...settings, run_cleansing: !settings.run_cleansing})}
                className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-primary hover:bg-primary/5 px-2 py-1 rounded"
              >
                {settings.run_cleansing ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                {settings.run_cleansing ? "Enabled" : "Disabled"}
              </button>
            </div>
            <Card className="border-slate-200 shadow-sm overflow-hidden">
              <CardContent className="p-4 space-y-4">
                <div className="space-y-2">
                  <Label className="text-xs">Handle Missing Values</Label>
                  <select 
                    disabled={!settings.run_cleansing}
                    value={settings.preprocessing.handle_missing}
                    onChange={e => setSettings({...settings, preprocessing: {...settings.preprocessing, handle_missing: e.target.value}})}
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
                    disabled={!settings.run_cleansing}
                    value={settings.preprocessing.normalization}
                    onChange={e => setSettings({...settings, preprocessing: {...settings.preprocessing, normalization: e.target.value}})}
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
          <section className={cn("space-y-4 transition-opacity", !settings.run_feature_selection && "opacity-50")}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                <Filter className="size-4" /> 2. Feature Selection
              </div>
              <button 
                onClick={() => setSettings({...settings, run_feature_selection: !settings.run_feature_selection})}
                className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-primary hover:bg-primary/5 px-2 py-1 rounded"
              >
                {settings.run_feature_selection ? <CheckSquare className="size-4" /> : <Square className="size-4" />}
                {settings.run_feature_selection ? "Enabled" : "Disabled"}
              </button>
            </div>
            <Card className="border-slate-200 shadow-sm">
              <CardContent className="p-4 space-y-4">
                <div className="space-y-2">
                  <Label className="text-xs flex justify-between">
                    Importance Threshold 
                    <span className="text-primary font-bold">{(settings.preprocessing.feature_selection_threshold || 0).toFixed(2)}</span>
                  </Label>
                  <input 
                    disabled={!settings.run_feature_selection}
                    type="range" min="0" max="0.5" step="0.01"
                    value={settings.preprocessing.feature_selection_threshold || 0}
                    onChange={e => setSettings({...settings, preprocessing: {...settings.preprocessing, feature_selection_threshold: parseFloat(e.target.value)}})}
                    className="w-full accent-primary disabled:opacity-50"
                  />
                  <p className="text-[10px] text-muted-foreground italic">Calculates feature importance and marks weak columns before workflow training.</p>
                </div>
              </CardContent>
            </Card>
          </section>
        </div>

        <div className="p-6 border-t bg-slate-50">
          <Button 
            className="w-full h-12 text-lg gap-3 shadow-lg" 
            onClick={onRun}
            disabled={isPending || !canRun}
          >
            {isPending ? 'Preparing Dataset...' : (
              <>
                <Sparkles className="size-5" />
                Run Prepare
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
