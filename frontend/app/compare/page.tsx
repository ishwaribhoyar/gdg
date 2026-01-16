'use client';

import { useState, useEffect, Suspense } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useSearchParams, useRouter } from 'next/navigation';
import { compareApi, batchApi, type ComparisonResponse, type BatchResponse, type SkippedBatch, type RankingResponse } from '@/lib/api';
import toast from 'react-hot-toast';
import dynamic from 'next/dynamic';
import {
    BarChart3, Trophy, AlertTriangle,
    CheckCircle, ArrowLeft, RefreshCw, Check, Award, XCircle
} from 'lucide-react';

// Lazy load heavy components for faster initial page load
const Chatbot = dynamic(() => import('@/components/Chatbot'), { ssr: false });

// Lazy load Recharts components
const BarChart = dynamic(() => import('recharts').then(mod => mod.BarChart), { ssr: false });
const Bar = dynamic(() => import('recharts').then(mod => mod.Bar), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(mod => mod.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(mod => mod.YAxis), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(mod => mod.CartesianGrid), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(mod => mod.Tooltip), { ssr: false });
const Legend = dynamic(() => import('recharts').then(mod => mod.Legend), { ssr: false });
const ResponsiveContainer = dynamic(() => import('recharts').then(mod => mod.ResponsiveContainer), { ssr: false });
const PieChart = dynamic(() => import('recharts').then(mod => mod.PieChart), { ssr: false });
const Pie = dynamic(() => import('recharts').then(mod => mod.Pie), { ssr: false });
const Cell = dynamic(() => import('recharts').then(mod => mod.Cell), { ssr: false });


// Format metric names for display
const formatMetricName = (key: string): string => {
    const map: Record<string, string> = {
        'fsr_score': 'FSR Score',
        'infrastructure_score': 'Infrastructure Score',
        'placement_index': 'Placement Index',
        'lab_compliance_index': 'Lab Compliance Index',
        'overall_score': 'Overall Score',
    };
    return map[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const CHART_COLORS = ['#0D9488', '#F97316', '#8B5CF6', '#059669', '#EC4899', '#3B82F6'];

const KPI_FILTER_OPTIONS = [
    { value: 'fsr', label: 'FSR Score' },
    { value: 'infrastructure', label: 'Infrastructure Score' },
    { value: 'placement', label: 'Placement Index' },
    { value: 'lab', label: 'Lab Compliance Index' },
    { value: 'overall', label: 'Overall Score' },
    { value: 'all', label: 'All KPIs (Weighted)' },
];

const TOP_N_OPTIONS = [2, 3, 5, 10];

// STRICT: Only show batches that are valid for comparison
// Must be: completed, has documents, sufficiency > 0, overall_score != null
const isValidBatch = (batch: BatchResponse): boolean => {
    // Basic checks
    if (batch.status !== 'completed') return false;
    if (batch.total_documents < 1) return false;

    // Additional validation will be done by backend
    // Frontend just filters out obvious invalid ones
    return true;
};

function ComparePageContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const batchIdsParam = searchParams.get('batch_ids') || '';

    const [allBatches, setAllBatches] = useState<BatchResponse[]>([]);
    const [selectedBatches, setSelectedBatches] = useState<string[]>([]);
    const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadingBatches, setLoadingBatches] = useState(true);
    const [ranking, setRanking] = useState<RankingResponse | null>(null);
    const [rankingLoading, setRankingLoading] = useState(false);
    const [rankingKpi, setRankingKpi] = useState<string>('overall');
    const [rankingTopN, setRankingTopN] = useState<number>(2);
    const [rankingWeights, setRankingWeights] = useState<Record<string, number>>({
        fsr_score: 1,
        infrastructure_score: 1,
        placement_index: 1,
        lab_compliance_index: 1,
        overall_score: 1,
    });

    useEffect(() => {
        const fetchBatches = async () => {
            try {
                const batches = await batchApi.list();
                // Only show valid batches (completed with documents)
                const validBatches = batches.filter(isValidBatch);
                setAllBatches(validBatches);
            } catch (err) {
                console.error(err);
                toast.error('Failed to fetch institutions');
            } finally {
                setLoadingBatches(false);
            }
        };
        fetchBatches();
    }, []);

    useEffect(() => {
        if (batchIdsParam) {
            const ids = batchIdsParam.split(',').filter(id => id.trim());
            setSelectedBatches(ids);
            if (ids.length >= 2) {
                fetchComparison(ids);
            }
        }
    }, [batchIdsParam]);

    const fetchComparison = async (ids: string[]) => {
        if (ids.length < 2) {
            setComparison(null);
            return;
        }
        setLoading(true);
        try {
            const data = await compareApi.get(ids);
            setComparison(data);

            // Only show toast for skipped batches if comparison is still valid
            // (if comparison is invalid, the UI will show a better message)
            if (data.valid_for_comparison && data.skipped_batches && data.skipped_batches.length > 0) {
                toast(`${data.skipped_batches.length} institution(s) excluded from comparison`, {
                    duration: 3000,
                    icon: '⚠️',
                });
            }

            // Don't show toast for validation errors - the UI card will display it better
        } catch (err) {
            console.error(err);
            toast.error('Failed to fetch comparison data');
            setComparison(null);
        } finally {
            setLoading(false);
        }
    };

    const getRankingKpiKey = (): string => {
        switch (rankingKpi) {
            case 'fsr':
                return 'fsr_score';
            case 'infrastructure':
                return 'infrastructure_score';
            case 'placement':
                return 'placement_index';
            case 'lab':
                return 'lab_compliance_index';
            case 'overall':
                return 'overall_score';
            default:
                return 'overall_score';
        }
    };

    const handleRanking = async () => {
        if (selectedBatches.length < 2) {
            toast.error('Select at least 2 institutions to rank');
            return;
        }

        setRankingLoading(true);
        try {
            const response = await compareApi.rank(
                selectedBatches,
                rankingKpi,
                rankingTopN,
                rankingKpi === 'all' ? rankingWeights : undefined
            );
            setRanking(response);

            if (response.insufficient_batches && response.insufficient_batches.length > 0) {
                toast(`${response.insufficient_batches.length} institution(s) skipped due to insufficient KPI data`, {
                    icon: '⚠️',
                    duration: 3500,
                });
            }
        } catch (err) {
            console.error(err);
            toast.error('Failed to fetch ranking');
        } finally {
            setRankingLoading(false);
        }
    };

    const updateWeight = (key: string, value: number) => {
        setRankingWeights(prev => ({
            ...prev,
            [key]: value,
        }));
    };

    const toggleBatch = (batchId: string) => {
        setSelectedBatches(prev =>
            prev.includes(batchId)
                ? prev.filter(id => id !== batchId)
                : prev.length < 10 ? [...prev, batchId] : prev
        );
    };

    const handleCompare = () => {
        if (selectedBatches.length < 2) {
            toast.error('Please select at least 2 institutions to compare');
            return;
        }
        router.push(`/compare?batch_ids=${selectedBatches.join(',')}`);
        fetchComparison(selectedBatches);
    };

    // Prepare chart data
    const barChartData = comparison?.valid_for_comparison && comparison.institutions && comparison.institutions.length > 0 && comparison.comparison_matrix
        ? Object.entries(comparison.comparison_matrix).map(([kpi]) => {
            const entry: Record<string, unknown> = { kpi: formatMetricName(kpi) };
            comparison.institutions.forEach((inst) => {
                if (inst && inst.short_label && inst.kpis) {
                    entry[inst.short_label] = inst.kpis[kpi] || 0;
                }
            });
            return entry;
        })
        : [];

    // Prepare pie chart data for overall performance distribution
    const overallPieData = comparison?.valid_for_comparison && comparison.institutions && comparison.institutions.length > 0
        ? comparison.institutions.map((inst, idx) => {
            if (!inst || !inst.kpis) return null;
            const kpiValues = Object.values(inst.kpis).filter((v): v is number => typeof v === 'number' && !isNaN(v) && v > 0);
            const avgScore = kpiValues.length > 0
                ? kpiValues.reduce((sum, val) => sum + val, 0) / kpiValues.length
                : 0;
            return {
                name: inst.short_label || `Institution ${idx + 1}`,
                value: Math.round(avgScore),
                fill: CHART_COLORS[idx % CHART_COLORS.length]
            };
        }).filter(item => item !== null) as Array<{ name: string; value: number; fill: string }>
        : [];

    const selectedKpiLabel = KPI_FILTER_OPTIONS.find(opt => opt.value === rankingKpi)?.label || 'Overall Score';
    const getDisplayedValue = (inst: any): number | null => {
        if (!inst) return null;
        if (rankingKpi === 'all') return inst.ranking_score ?? null;
        const key = getRankingKpiKey();
        return inst[key as keyof typeof inst] as number | null;
    };

    return (
        <div className="min-h-screen bg-gradient-soft py-8">
            <div className="container mx-auto px-4 max-w-7xl">
                {/* Header */}
                <div className="flex items-center gap-4 mb-8">
                    <button onClick={() => router.push('/')} className="p-2 bg-white rounded-xl shadow-soft hover:shadow-soft-lg transition-all">
                        <ArrowLeft className="w-5 h-5 text-gray-600" />
                    </button>
                    <div>
                        <h1 className="text-3xl font-bold text-gray-800">Institution Comparison</h1>
                        <p className="text-gray-600">Compare KPIs across completed institutions</p>
                    </div>
                </div>

                {/* Institution Selection */}
                <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8">
                    <h2 className="text-xl font-semibold text-gray-800 mb-2">Select Institutions to Compare</h2>
                    <p className="text-sm text-gray-500 mb-4">Only completed institutions with processed documents are shown</p>

                    {loadingBatches ? (
                        <div className="flex items-center justify-center py-8">
                            <RefreshCw className="w-6 h-6 text-primary animate-spin" />
                            <span className="ml-2 text-gray-600">Loading institutions...</span>
                        </div>
                    ) : allBatches.length === 0 ? (
                        <div className="text-center py-8">
                            <XCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                            <p className="text-gray-500">No completed institutions available for comparison.</p>
                            <p className="text-sm text-gray-400">Process some documents first to enable comparison.</p>
                        </div>
                    ) : (
                        <>
                            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
                                {allBatches.map(batch => {
                                    const isSelected = selectedBatches.includes(batch.batch_id);
                                    return (
                                        <div
                                            key={batch.batch_id}
                                            onClick={() => toggleBatch(batch.batch_id)}
                                            className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${isSelected
                                                ? 'border-primary bg-primary-50'
                                                : 'border-gray-200 hover:border-primary-light bg-white'
                                                }`}
                                        >
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                                                        <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${batch.mode === 'aicte' ? 'bg-primary-100 text-primary' :
                                                            batch.mode === 'ugc' ? 'bg-accent-100 text-accent' :
                                                                'bg-purple-100 text-purple-600'
                                                            }`}>
                                                            {batch.mode}
                                                        </span>
                                                        <span className="px-2 py-0.5 rounded text-xs bg-green-50 text-green-600">
                                                            ✓ Completed
                                                        </span>
                                                        {batch.data_source === 'system' && (
                                                            <span className="px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-600 font-medium">
                                                                System
                                                            </span>
                                                        )}
                                                        <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
                                                            {batch.total_documents} doc{batch.total_documents !== 1 ? 's' : ''}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm text-gray-700 font-medium truncate">
                                                        {batch.institution_name || `Institution #${batch.batch_id.slice(-8)}`}
                                                    </p>
                                                    <p className="text-xs text-gray-500 mt-1">
                                                        {new Date(batch.created_at).toLocaleDateString()}
                                                    </p>
                                                </div>
                                                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${isSelected ? 'bg-primary border-primary' : 'border-gray-300'
                                                    }`}>
                                                    {isSelected && <Check className="w-4 h-4 text-white" />}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="flex items-center justify-between">
                                <p className="text-sm text-gray-500">
                                    Selected: {selectedBatches.length} institution{selectedBatches.length !== 1 ? 's' : ''}
                                    {selectedBatches.length < 2 && ' (need at least 2)'}
                                </p>
                                <button
                                    onClick={handleCompare}
                                    disabled={selectedBatches.length < 2 || loading}
                                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-primary to-primary-light text-white rounded-xl font-medium hover:shadow-glow-teal disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                >
                                    {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <BarChart3 className="w-5 h-5" />}
                                    Compare Institutions
                                </button>
                            </div>
                        </>
                    )}
                </div>

                {/* Skipped Batches Warning */}
                {comparison && comparison.skipped_batches && comparison.skipped_batches.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6">
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div>
                                <h3 className="font-semibold text-amber-800">Some institutions were excluded</h3>
                                <ul className="mt-2 space-y-1">
                                    {comparison.skipped_batches.map((sb: SkippedBatch) => (
                                        <li key={sb.batch_id} className="text-sm text-amber-700">
                                            • {sb.batch_id.slice(-12)}: {sb.reason.replace(/_/g, ' ')}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>
                )}

                {/* Invalid Comparison Warning */}
                {comparison && !comparison.valid_for_comparison && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 mb-6">
                        <div className="flex items-start gap-4">
                            <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <h3 className="font-semibold text-amber-800 text-lg mb-2">Comparison Not Available</h3>
                                <p className="text-amber-700 mb-3">{comparison.validation_message}</p>
                                {comparison.validation_message?.includes('Need at least 2') && (
                                    <div className="bg-white rounded-xl p-4 border border-amber-100">
                                        <p className="text-sm text-amber-800 font-medium mb-2">To enable comparison:</p>
                                        <ul className="text-sm text-amber-700 space-y-1 list-disc list-inside">
                                            <li>Process documents for at least 2 different institutions</li>
                                            <li>Ensure all selected institutions have completed processing</li>
                                            <li>Make sure each institution has at least 1 processed document</li>
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Comparison Results - Only show if valid */}
                {comparison && comparison.valid_for_comparison && comparison.institutions.length >= 2 && (
                    <>
                        {/* Winner Banner */}
                        {comparison.winner_label && (
                            <div className="bg-gradient-to-r from-secondary to-green-500 text-white rounded-3xl p-6 mb-8">
                                <div className="flex items-center gap-4">
                                    <div className="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center">
                                        <Trophy className="w-10 h-10 text-yellow-300" />
                                    </div>
                                    <div>
                                        <h3 className="text-2xl font-bold">🏆 Best Overall Institution</h3>
                                        <p className="text-xl opacity-90">{comparison.winner_label} - {comparison.winner_name}</p>
                                    </div>
                                </div>
                                {comparison.interpretation?.notes && comparison.interpretation.notes.length > 0 && (
                                    <div className="mt-4 pt-4 border-t border-white/20">
                                        {comparison.interpretation.notes.map((note, i) => (
                                            <p key={i} className="text-sm opacity-80">{note}</p>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Top Performers */}
                        <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8">
                            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-4">
                                <div>
                                    <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
                                        <Trophy className="w-6 h-6 text-yellow-500" />
                                        Top Performers
                                    </h2>
                                    <p className="text-sm text-gray-500">Rank institutions using real KPI scores only</p>
                                </div>
                                <div className="flex flex-wrap gap-3">
                                    <select
                                        value={rankingKpi}
                                        onChange={(e) => setRankingKpi(e.target.value)}
                                        className="px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                    >
                                        {KPI_FILTER_OPTIONS.map(opt => (
                                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                                        ))}
                                    </select>
                                    <select
                                        value={rankingTopN}
                                        onChange={(e) => setRankingTopN(Number(e.target.value))}
                                        className="px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                    >
                                        {TOP_N_OPTIONS.map(n => (
                                            <option key={n} value={n}>Top {n}</option>
                                        ))}
                                    </select>
                                    <button
                                        onClick={handleRanking}
                                        disabled={rankingLoading || selectedBatches.length < 2}
                                        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary-light disabled:opacity-50 disabled:cursor-not-allowed transition"
                                    >
                                        {rankingLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trophy className="w-4 h-4" />}
                                        Show Top Institutions
                                    </button>
                                </div>
                            </div>

                            {rankingKpi === 'all' && (
                                <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-3 bg-gray-50 border border-gray-100 rounded-2xl p-4 mb-4">
                                    {[
                                        { key: 'fsr_score', label: 'FSR' },
                                        { key: 'infrastructure_score', label: 'Infrastructure' },
                                        { key: 'placement_index', label: 'Placement' },
                                        { key: 'lab_compliance_index', label: 'Lab Compliance' },
                                        { key: 'overall_score', label: 'Overall' },
                                    ].map(item => (
                                        <div key={item.key} className="flex flex-col">
                                            <label className="text-xs text-gray-500 mb-1">{item.label} Weight (0-3)</label>
                                            <input
                                                type="number"
                                                min={0}
                                                max={3}
                                                step={0.5}
                                                value={rankingWeights[item.key]}
                                                onChange={(e) => updateWeight(item.key, Math.max(0, Math.min(3, Number(e.target.value))))}
                                                className="px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                            />
                                        </div>
                                    ))}
                                </div>
                            )}

                            {ranking && ranking.institutions.length > 0 && (
                                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {ranking.institutions.map((inst, idx) => (
                                        <div key={inst.batch_id} className="rounded-2xl border border-gray-100 p-4 bg-gradient-to-br from-gray-50 to-white shadow-soft">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold"
                                                        style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}>
                                                        #{idx + 1}
                                                    </div>
                                                    <div>
                                                        <p className="text-sm text-gray-500">{inst.short_label}</p>
                                                        <p className="text-base font-semibold text-gray-800 truncate">{inst.name}</p>
                                                    </div>
                                                </div>
                                                <span className="text-xs px-2 py-1 rounded bg-primary-50 text-primary">{inst.mode.toUpperCase()}</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3 mb-3">
                                                <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
                                                    <p className="text-xs text-gray-500">Ranking Score</p>
                                                    <p className="text-xl font-bold text-primary">{inst.ranking_score.toFixed(2)}</p>
                                                </div>
                                                <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
                                                    <p className="text-xs text-gray-500">{selectedKpiLabel}</p>
                                                    <p className="text-xl font-bold text-gray-800">
                                                        {(() => {
                                                            const v = getDisplayedValue(inst);
                                                            return v !== null && v !== undefined ? v.toFixed(1) : '—';
                                                        })()}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3">
                                                <div>
                                                    <p className="text-xs font-semibold text-green-700 flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Strengths</p>
                                                    <ul className="mt-1 space-y-1">
                                                        {(inst.strengths || []).slice(0, 2).map((s, i) => (
                                                            <li key={i} className="text-xs text-gray-600">{s}</li>
                                                        ))}
                                                        {(!inst.strengths || inst.strengths.length === 0) && (
                                                            <li className="text-xs text-gray-400 italic">No high KPIs</li>
                                                        )}
                                                    </ul>
                                                </div>
                                                <div>
                                                    <p className="text-xs font-semibold text-amber-700 flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> Weaknesses</p>
                                                    <ul className="mt-1 space-y-1">
                                                        {(inst.weaknesses || []).slice(0, 2).map((w, i) => (
                                                            <li key={i} className="text-xs text-gray-600">{w}</li>
                                                        ))}
                                                        {(!inst.weaknesses || inst.weaknesses.length === 0) && (
                                                            <li className="text-xs text-gray-400 italic">No low KPIs</li>
                                                        )}
                                                    </ul>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {ranking && ranking.institutions.length === 0 && (
                                <div className="text-sm text-gray-500">No institutions available for the selected KPI filter.</div>
                            )}

                            {ranking && ranking.insufficient_batches && ranking.insufficient_batches.length > 0 && (
                                <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
                                    {ranking.insufficient_batches.length} institution(s) skipped due to insufficient KPI data.
                                </div>
                            )}
                        </div>

                        {/* KPI Bar Chart */}
                        {barChartData.length > 0 && (
                            <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8">
                                <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                    <BarChart3 className="w-6 h-6 text-primary" />
                                    KPI Comparison
                                </h2>
                                <ResponsiveContainer width="100%" height={350}>
                                    <BarChart data={barChartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                                        <XAxis dataKey="kpi" tick={{ fill: '#6B7280', fontSize: 12 }} />
                                        <YAxis tick={{ fill: '#6B7280', fontSize: 12 }} domain={[0, 100]} />
                                        <Tooltip />
                                        <Legend />
                                        {comparison.institutions.map((inst, idx) => (
                                            <Bar
                                                key={inst.batch_id}
                                                dataKey={inst.short_label}
                                                fill={CHART_COLORS[idx % CHART_COLORS.length]}
                                                radius={[4, 4, 0, 0]}
                                            />
                                        ))}
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Overall Performance Pie Chart */}
                        {overallPieData.length > 0 && (
                            <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8">
                                <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                    <Trophy className="w-6 h-6 text-primary" />
                                    Overall Performance Distribution
                                </h2>
                                <ResponsiveContainer width="100%" height={400}>
                                    <PieChart>
                                        <Pie
                                            data={overallPieData}
                                            cx="50%"
                                            cy="50%"
                                            labelLine={false}
                                            label={({ name, value, percent }) => `${name}: ${value}${percent !== undefined ? ` (${(percent * 100).toFixed(0)}%)` : ''}`}
                                            outerRadius={120}
                                            fill="#8884d8"
                                            dataKey="value"
                                        >
                                            {overallPieData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip
                                            formatter={(value: number, name: string, props: { payload?: { percent?: number } }) => {
                                                const percent = props?.payload?.percent || 0;
                                                return [`${value.toFixed(1)} (${(percent * 100).toFixed(0)}%)`, 'Average Score'];
                                            }}
                                        />
                                        <Legend />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Detailed Comparison Table */}
                        <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8 overflow-x-auto">
                            <h2 className="text-xl font-semibold text-gray-800 mb-4">Detailed Comparison</h2>
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b-2 border-gray-100">
                                        <th className="text-left py-3 px-4 font-semibold text-gray-700">Metric</th>
                                        {comparison.institutions.map((inst, idx) => (
                                            <th key={inst.batch_id} className="text-center py-3 px-4">
                                                <div className="flex flex-col items-center">
                                                    <span
                                                        className="font-bold text-lg"
                                                        style={{ color: CHART_COLORS[idx % CHART_COLORS.length] }}
                                                    >
                                                        {inst.short_label}
                                                    </span>
                                                    <span className="text-xs text-gray-500">{inst.mode.toUpperCase()}</span>
                                                </div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(comparison.comparison_matrix).map(([kpi]) => {
                                        const values = comparison.institutions.map(i => i.kpis[kpi]).filter(v => v !== null) as number[];
                                        const maxVal = Math.max(...values);
                                        const minVal = Math.min(...values);

                                        return (
                                            <tr key={kpi} className="border-b border-gray-50 hover:bg-gray-50">
                                                <td className="py-3 px-4 font-medium text-gray-800">{formatMetricName(kpi)}</td>
                                                {comparison.institutions.map((inst) => {
                                                    const val = inst.kpis[kpi];
                                                    const isMax = val === maxVal && val !== null;
                                                    const isMin = val === minVal && val !== null && minVal < 60;

                                                    return (
                                                        <td
                                                            key={inst.batch_id}
                                                            className={`text-center py-3 px-4 font-medium ${isMax ? 'text-green-600 bg-green-50' :
                                                                isMin ? 'text-red-500 bg-red-50' :
                                                                    'text-gray-600'
                                                                }`}
                                                        >
                                                            {val !== null ? (
                                                                <>
                                                                    {val.toFixed(1)}
                                                                    {isMax && <span className="ml-1">🟢</span>}
                                                                    {isMin && <span className="ml-1">🔴</span>}
                                                                </>
                                                            ) : <span className="text-gray-400">-</span>}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        );
                                    })}
                                    {/* Summary Rows */}
                                    <tr className="border-t-2 border-gray-200 bg-gray-50">
                                        <td className="py-3 px-4 font-semibold text-gray-800">Sufficiency %</td>
                                        {comparison.institutions.map(inst => (
                                            <td key={inst.batch_id} className="text-center py-3 px-4 font-medium text-gray-700">
                                                {inst.sufficiency_percent.toFixed(1)}%
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="bg-gray-50">
                                        <td className="py-3 px-4 font-semibold text-gray-800">Compliance Issues</td>
                                        {comparison.institutions.map(inst => (
                                            <td key={inst.batch_id} className="text-center py-3 px-4">
                                                <span className={`px-3 py-1 rounded-full text-sm font-medium ${inst.compliance_count === 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                                                    }`}>
                                                    {inst.compliance_count}
                                                </span>
                                            </td>
                                        ))}
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        {/* Category Winners */}
                        {comparison.interpretation?.category_winners && comparison.interpretation.category_winners.length > 0 && (
                            <div className="bg-white rounded-3xl shadow-soft-lg p-6 mb-8">
                                <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                                    <Award className="w-6 h-6 text-yellow-500" />
                                    Category Leaders
                                </h2>
                                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {comparison.interpretation.category_winners.map((cw) => (
                                        <div key={cw.kpi_key} className="bg-gradient-to-br from-gray-50 to-white rounded-2xl p-4 border border-gray-100">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm font-medium text-gray-600">{cw.kpi_name}</span>
                                                <Trophy className="w-4 h-4 text-yellow-500" />
                                            </div>
                                            <div className="text-lg font-bold text-gray-800">{cw.winner_label}</div>
                                            <div className="text-sm text-primary font-medium">{cw.winner_value.toFixed(1)} points</div>
                                            {cw.is_tie && (
                                                <div className="text-xs text-gray-500 mt-1">Tied with: {cw.tied_with.join(', ')}</div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Institution Cards */}
                        <h2 className="text-xl font-semibold text-gray-800 mb-4">Institution Analysis</h2>
                        <div className="grid md:grid-cols-2 gap-6">
                            {comparison.institutions.map((inst, idx) => (
                                <div
                                    key={inst.batch_id}
                                    className={`bg-white rounded-3xl shadow-soft-lg p-6 ${comparison.winner_institution === inst.batch_id ? 'ring-2 ring-green-400' : ''
                                        }`}
                                >
                                    <div className="flex items-center gap-3 mb-4">
                                        <div
                                            className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg"
                                            style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
                                        >
                                            {inst.short_label.slice(0, 3)}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h3 className="text-lg font-bold text-gray-800 truncate">{inst.short_label}</h3>
                                            <p className="text-sm text-gray-500 truncate">{inst.institution_name} • {inst.mode.toUpperCase()}</p>
                                        </div>
                                        {comparison.winner_institution === inst.batch_id && (
                                            <Trophy className="w-6 h-6 text-yellow-500 flex-shrink-0" />
                                        )}
                                    </div>

                                    <div className="flex items-center gap-4 mb-4">
                                        <div className="flex-1 bg-gray-50 rounded-xl p-3 text-center">
                                            <div className="text-2xl font-bold text-primary">{inst.overall_score.toFixed(1)}</div>
                                            <div className="text-xs text-gray-500">Overall</div>
                                        </div>
                                        <div className="flex-1 bg-gray-50 rounded-xl p-3 text-center">
                                            <div className="text-2xl font-bold text-secondary">{inst.sufficiency_percent.toFixed(0)}%</div>
                                            <div className="text-xs text-gray-500">Sufficiency</div>
                                        </div>
                                        <div className="flex-1 bg-gray-50 rounded-xl p-3 text-center">
                                            <div className={`text-2xl font-bold ${inst.compliance_count === 0 ? 'text-green-600' : 'text-red-500'}`}>
                                                {inst.compliance_count}
                                            </div>
                                            <div className="text-xs text-gray-500">Issues</div>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <h4 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-1">
                                                <CheckCircle className="w-4 h-4" /> Strengths
                                            </h4>
                                            <ul className="space-y-1">
                                                {inst.strengths.slice(0, 3).map((s, i) => (
                                                    <li key={i} className="text-xs text-gray-600 pl-3 border-l-2 border-green-400">{s}</li>
                                                ))}
                                                {inst.strengths.length === 0 && (
                                                    <li className="text-xs text-gray-400 italic">No strengths identified</li>
                                                )}
                                            </ul>
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-semibold text-amber-700 mb-2 flex items-center gap-1">
                                                <AlertTriangle className="w-4 h-4" /> Improve
                                            </h4>
                                            <ul className="space-y-1">
                                                {inst.weaknesses.slice(0, 3).map((w, i) => (
                                                    <li key={i} className="text-xs text-gray-600 pl-3 border-l-2 border-amber-400">{w}</li>
                                                ))}
                                                {inst.weaknesses.length === 0 && (
                                                    <li className="text-xs text-gray-400 italic">No issues identified</li>
                                                )}
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Chatbot - Show if we have at least one batch selected */}
            {selectedBatches.length > 0 && (
                <Chatbot
                    batchId={selectedBatches[0]}
                    currentPage="compare"
                    comparisonBatchIds={selectedBatches.length >= 2 ? selectedBatches : undefined}
                />
            )}
        </div>
    );
}

export default function ComparePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-gradient-soft flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-3 border-primary border-t-transparent" />
            </div>
        }>
            <ComparePageContent />
        </Suspense>
    );
}
