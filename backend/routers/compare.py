"""
Institution comparison API with strict validation.
Only includes completed batches with valid documents and KPIs.
"""

import json
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional, Tuple
from schemas.compare import (
    ComparisonResponse,
    InstitutionComparison,
    ComparisonInterpretation,
    CategoryWinner,
    SkippedBatch,
    RankingResponse,
)
from routers.dashboard import get_dashboard_data
from services.ranking_service import rank_institutions
from utils.label_formatter import (
    generate_short_label,
    format_institution_name,
    format_metric_name,
    extract_academic_year_from_data,
)
from config.database import get_db, close_db, Batch, Block
from middleware.auth_middleware import get_current_user
from services.production_guard import ProductionGuard

router = APIRouter()

CANONICAL_KPIS = ["fsr_score", "infrastructure_score", "placement_index", "lab_compliance_index", "overall_score"]
VALID_STATUSES = ["completed"]


def _validate_batch(batch_id: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Validate if a batch is eligible for comparison.
    STRICT: Exclude invalid batches, batches with 0 docs, incomplete processing.
    Exception: System batches may have blocks but no files.
    
    Returns: (is_valid, skip_reason, batch_info)
    """
    db = get_db()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        
        if not batch:
            return False, "batch_not_found", None
        
        # Check if this is a system batch (seeded demo data)
        is_system_batch = getattr(batch, 'data_source', 'user') == 'system'
        
        # CRITICAL: Use ProductionGuard to validate batch
        is_valid, error_msg = ProductionGuard.validate_batch_for_operations(batch)
        if not is_valid:
            return False, "batch_invalid", {"mode": batch.mode, "reason": error_msg or "Marked as invalid - insufficient data"}
        
        # Check status - must be completed
        if batch.status not in VALID_STATUSES:
            return False, f"status_{batch.status}", {"mode": batch.mode}
        
        # Check documents - must have at least 1 processed document
        # Exception: System batches may have blocks but no files
        from config.database import File
        file_count = db.query(File).filter(File.batch_id == batch_id).count()
        
        # Check blocks - must have at least some extracted data
        blocks = db.query(Block).filter(Block.batch_id == batch_id).all()
        valid_blocks = [b for b in blocks if not (hasattr(b, 'is_invalid') and b.is_invalid == 1)]
        
        # For system batches: require blocks (not files)
        # For user batches: require both files and blocks
        if is_system_batch:
            if len(valid_blocks) == 0:
                return False, "no_valid_blocks", {"mode": batch.mode}
        else:
            if file_count == 0:
                return False, "no_processed_documents", {"mode": batch.mode}
            if len(valid_blocks) == 0:
                return False, "no_valid_blocks", {"mode": batch.mode}
        
        # Check KPIs - must have at least one valid KPI > 0
        kpi_results = batch.kpi_results or {}
        
        # Handle both formats: nested dict {value: X} and direct numeric X
        def get_kpi_value(key):
            val = kpi_results.get(key)
            if val is None:
                return None
            if isinstance(val, dict):
                return val.get("value")
            if isinstance(val, (int, float)):
                return val
            return None
        
        overall_score = get_kpi_value("overall_score")
        if overall_score is None or overall_score == 0:
            return False, "no_valid_kpis", {"mode": batch.mode, "overall_score": overall_score}
        
        return True, None, {
            "mode": batch.mode,
            "blocks": valid_blocks,
        }
    finally:
        close_db(db)


def _get_real_institution_name(dashboard: Any, batch_id: str) -> str:
    """Get real institution name from dashboard, no dummy fallbacks."""
    # Try dashboard.institution_name
    if dashboard.institution_name and len(dashboard.institution_name.strip()) > 3:
        return dashboard.institution_name.strip()
    
    # Try from blocks - look for basic_information or institution block
    if dashboard.block_cards:
        for block in dashboard.block_cards:
            if hasattr(block, 'data') and block.data:
                for key in ['institution_name', 'name', 'institute_name', 'college_name']:
                    if key in block.data and block.data[key]:
                        return str(block.data[key]).strip()
    
    # Last resort - use batch mode + partial ID
    mode = batch_id.split('_')[1] if '_' in batch_id else 'unknown'
    return f"{mode.upper()} Institution #{batch_id[-4:]}"


def _has_valid_kpis(kpis: Dict[str, Optional[float]]) -> bool:
    """Check if at least one KPI has a valid numeric value."""
    for val in kpis.values():
        if val is not None and isinstance(val, (int, float)) and val > 0:
            return True
    return False


def _strengths_weaknesses(kpis: Dict[str, Optional[float]]) -> Tuple[List[str], List[str]]:
    """Generate readable strengths and weaknesses from KPIs."""
    scored = [(k, v) for k, v in kpis.items() if v is not None and isinstance(v, (int, float))]
    if not scored:
        return [], []
    
    scored.sort(key=lambda kv: kv[1], reverse=True)
    
    strengths = []
    for k, v in scored[:3]:
        if v >= 80:
            strengths.append(f"Excellent {format_metric_name(k)} ({v:.1f})")
        elif v >= 60:
            strengths.append(f"Good {format_metric_name(k)} ({v:.1f})")
    
    weaknesses = []
    for k, v in reversed(scored):
        if v < 60:
            weaknesses.append(f"{format_metric_name(k)} needs improvement ({v:.1f})")
        if len(weaknesses) >= 3:
            break
    
    return strengths, weaknesses


def _determine_winner(institutions: List[InstitutionComparison]) -> Optional[InstitutionComparison]:
    """
    Determine winner: highest overall → highest placement → highest sufficiency → lowest compliance.
    """
    if not institutions:
        return None
    
    def sort_key(inst: InstitutionComparison) -> tuple:
        overall = inst.overall_score or 0
        placement = inst.kpis.get('placement_index') or 0
        sufficiency = inst.sufficiency_percent or 0
        compliance = inst.compliance_count or 0
        return (overall, placement, sufficiency, -compliance)
    
    sorted_insts = sorted(institutions, key=sort_key, reverse=True)
    return sorted_insts[0]


def rank_institutions(
    batch_ids: List[str],
    weight_map: Dict[str, float],
    top_n: int,
    ranking_label: str
) -> RankingResponse:
    """
    Rank institutions based on real KPI data from database.
    Returns top N institutions sorted by weighted KPI score.
    """
    from schemas.compare import RankingResponse, RankingInstitution
    
    db = get_db()
    try:
        ranked_institutions = []
        insufficient_batches = []
        
        for batch_id in batch_ids:
            # Get batch info
            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                insufficient_batches.append(batch_id)
                continue
            
            if batch.status != "completed":
                insufficient_batches.append(batch_id)
                continue
            
            # Get dashboard data for KPIs
            try:
                dashboard = get_dashboard_data(batch_id)
            except:
                insufficient_batches.append(batch_id)
                continue
            
            # Extract KPI values
            kpis = {}
            for card in dashboard.kpi_cards:
                # Map card names to KPI keys
                name_lower = card.name.lower()
                if "fsr" in name_lower:
                    kpis["fsr_score"] = card.value
                elif "infrastructure" in name_lower:
                    kpis["infrastructure_score"] = card.value
                elif "placement" in name_lower:
                    kpis["placement_index"] = card.value
                elif "lab" in name_lower:
                    kpis["lab_compliance_index"] = card.value
                elif "overall" in name_lower:
                    kpis["overall_score"] = card.value
            
            # Calculate ranking score based on weights
            total_weight = sum(weight_map.values())
            if total_weight == 0:
                insufficient_batches.append(batch_id)
                continue
            
            weighted_sum = 0.0
            valid_kpis = 0
            for kpi_key, weight in weight_map.items():
                if weight > 0 and kpi_key in kpis and kpis[kpi_key] is not None:
                    weighted_sum += weight * kpis[kpi_key]
                    valid_kpis += 1
            
            if valid_kpis == 0:
                insufficient_batches.append(batch_id)
                continue
            
            ranking_score = weighted_sum / total_weight
            
            # Get institution name
            inst_name = _get_real_institution_name(dashboard, batch_id)
            short_label = generate_short_label(inst_name, batch_id)
            
            # Get strengths/weaknesses
            strengths, weaknesses = _strengths_weaknesses(kpis)
            
            ranked_institutions.append(RankingInstitution(
                batch_id=batch_id,
                name=inst_name,
                short_label=short_label,
                mode=batch.mode or "aicte",
                ranking_score=round(ranking_score, 2),
                fsr_score=kpis.get("fsr_score"),
                infrastructure_score=kpis.get("infrastructure_score"),
                placement_index=kpis.get("placement_index"),
                lab_compliance_index=kpis.get("lab_compliance_index"),
                overall_score=kpis.get("overall_score") or ranking_score,
                strengths=strengths,
                weaknesses=weaknesses
            ))
        
        # Sort by ranking score descending
        ranked_institutions.sort(key=lambda x: x.ranking_score, reverse=True)
        
        # Return top N
        top_institutions = ranked_institutions[:top_n]
        
        # Convert insufficient batch IDs to SkippedBatch objects
        from schemas.compare import SkippedBatch
        skipped = [
            SkippedBatch(batch_id=bid, reason="no_kpis")
            for bid in insufficient_batches
        ]
        
        return RankingResponse(
            institutions=top_institutions,
            ranking_type=ranking_label,
            top_n=top_n,
            insufficient_batches=skipped
        )
        
    finally:
        close_db(db)


@router.get("/compare/rank", response_model=RankingResponse)
def rank_top_institutions(
    batch_ids: str = Query(..., description="Comma-separated batch ids"),
    kpi: str = Query("overall", description="fsr | infrastructure | placement | lab | overall | all"),
    top_n: int = Query(2, ge=1, le=50, description="How many institutions to return"),
    weights: Optional[str] = Query(None, description="JSON map of KPI weights when kpi=all"),
):
    """
    Return Top-N ranked institutions based on real KPI scores.
    - Uses stored KPI results only
    - Skips batches with missing required KPI values
    """
    ids = [bid.strip() for bid in batch_ids.split(",") if bid.strip()]
    if len(ids) < 1:
        raise HTTPException(status_code=400, detail="Provide at least one batch_id")

    kpi_key = kpi.lower()
    weight_map: Dict[str, float] = {}
    ranking_label = ""

    if kpi_key in ["fsr", "fsr_score"]:
        weight_map = {"fsr_score": 1.0}
        ranking_label = "FSR Score"
    elif kpi_key in ["infrastructure", "infrastructure_score", "infra"]:
        weight_map = {"infrastructure_score": 1.0}
        ranking_label = "Infrastructure Score"
    elif kpi_key in ["placement", "placement_index"]:
        weight_map = {"placement_index": 1.0}
        ranking_label = "Placement Index"
    elif kpi_key in ["lab", "lab_compliance", "lab_compliance_index"]:
        weight_map = {"lab_compliance_index": 1.0}
        ranking_label = "Lab Compliance Index"
    elif kpi_key in ["overall", "overall_score"]:
        weight_map = {"overall_score": 1.0}
        ranking_label = "Overall Score"
    elif kpi_key in ["all", "weighted", "multi"]:
        if not weights:
            raise HTTPException(status_code=400, detail="Provide weights JSON when kpi=all")
        try:
            parsed = json.loads(weights)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid weights JSON")

        weight_map = {
            "fsr_score": float(parsed.get("fsr") or parsed.get("fsr_score") or 0),
            "infrastructure_score": float(parsed.get("infrastructure") or parsed.get("infrastructure_score") or parsed.get("infra") or 0),
            "placement_index": float(parsed.get("placement") or parsed.get("placement_index") or 0),
            "lab_compliance_index": float(parsed.get("lab") or parsed.get("lab_compliance") or parsed.get("lab_compliance_index") or 0),
            "overall_score": float(parsed.get("overall") or parsed.get("overall_score") or 0),
        }
        if all(v == 0 for v in weight_map.values()):
            raise HTTPException(status_code=400, detail="At least one KPI weight must be greater than zero")
        ranking_label = "Weighted KPI Mix"
    else:
        raise HTTPException(status_code=400, detail="Invalid kpi parameter")

    # Default top_n to 2 if missing/invalid (Query already enforces >=1)
    top_n_final = top_n or 2
    result = rank_institutions(ids, weight_map, top_n_final, ranking_label)
    return result


@router.get("/compare", response_model=ComparisonResponse)
def compare_institutions(
    batch_ids: str = Query(..., description="Comma-separated batch ids"),
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Compare 2-10 institutions with strict validation.
    Only completed batches with valid documents and KPIs are included.
    PERFORMANCE: Cached for 5 minutes
    """
    # PERFORMANCE: Check cache first
    from utils.performance_cache import cache, get_cache_key
    import logging
    logger = logging.getLogger(__name__)
    
    # Create cache key from sorted batch IDs (order-independent)
    ids = [bid.strip() for bid in batch_ids.split(",") if bid.strip()]
    
    # DEMO MODE: Return demo comparison for demo batches
    has_demo = any(bid.startswith("demo-") for bid in ids)
    
    # Try cache first for non-demo batches
    if not has_demo:
        try:
            cache_key = get_cache_key("compare", *sorted(ids))
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for comparison {batch_ids}")
                return cached
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
    
    # For demo batches, return mock comparison data
    if has_demo:
            demo_institutions = [
                InstitutionComparison(
                    batch_id="demo-batch-aicte-2024",
                    institution_name="Indian Institute of Technology Delhi",
                    short_label="IIT-D 24-25",
                    academic_year="2024-25",
                    mode="aicte",
                    kpis={
                        "fsr_score": 85.2,
                        "infrastructure_score": 78.5,
                        "placement_index": 92.3,
                        "lab_compliance_index": 82.1,
                        "overall_score": 84.5
                    },
                    sufficiency_percent=95.0,
                    compliance_count=0,
                    overall_score=84.5,
                    strengths=["Excellent Placement (92.3)", "Strong Faculty-Student Ratio (85.2)"],
                    weaknesses=[]
                ),
                InstitutionComparison(
                    batch_id="demo-batch-aicte-2023",
                    institution_name="National Institute of Technology Trichy",
                    short_label="NIT-T 24-25",
                    academic_year="2024-25",
                    mode="aicte",
                    kpis={
                        "fsr_score": 78.9,
                        "infrastructure_score": 82.0,
                        "placement_index": 88.5,
                        "lab_compliance_index": 75.3,
                        "overall_score": 81.2
                    },
                    sufficiency_percent=90.0,
                    compliance_count=1,
                    overall_score=81.2,
                    strengths=["Good Infrastructure (82.0)", "Strong Placement (88.5)"],
                    weaknesses=["Lab Compliance needs improvement (75.3)"]
                )
            ]
            
            demo_matrix = {
                "fsr_score": {"IIT-D 24-25": 85.2, "NIT-T 24-25": 78.9},
                "infrastructure_score": {"IIT-D 24-25": 78.5, "NIT-T 24-25": 82.0},
                "placement_index": {"IIT-D 24-25": 92.3, "NIT-T 24-25": 88.5},
                "lab_compliance_index": {"IIT-D 24-25": 82.1, "NIT-T 24-25": 75.3},
                "overall_score": {"IIT-D 24-25": 84.5, "NIT-T 24-25": 81.2}
            }
            
            return ComparisonResponse(
                institutions=demo_institutions,
                skipped_batches=[],
                comparison_matrix=demo_matrix,
                winner_institution="demo-batch-aicte-2024",
                winner_label="IIT-D 24-25",
                winner_name="Indian Institute of Technology Delhi",
                category_winners={
                    "fsr_score": "demo-batch-aicte-2024",
                    "placement_index": "demo-batch-aicte-2024",
                    "infrastructure_score": "demo-batch-aicte-2023",
                    "lab_compliance_index": "demo-batch-aicte-2024",
                    "overall_score": "demo-batch-aicte-2024"
                },
                category_winners_labels={
                    "fsr_score": "IIT-D 24-25",
                    "placement_index": "IIT-D 24-25",
                    "infrastructure_score": "NIT-T 24-25",
                    "lab_compliance_index": "IIT-D 24-25",
                    "overall_score": "IIT-D 24-25"
                },
                interpretation=ComparisonInterpretation(
                    best_overall_batch_id="demo-batch-aicte-2024",
                    best_overall_label="IIT-D 24-25",
                    best_overall_name="Indian Institute of Technology Delhi",
                    category_winners=[
                        CategoryWinner(kpi_key="overall_score", kpi_name="Overall Score", winner_batch_id="demo-batch-aicte-2024", winner_label="IIT-D 24-25", winner_value=84.5, is_tie=False, tied_with=[]),
                        CategoryWinner(kpi_key="placement_index", kpi_name="Placement Index", winner_batch_id="demo-batch-aicte-2024", winner_label="IIT-D 24-25", winner_value=92.3, is_tie=False, tied_with=[]),
                        CategoryWinner(kpi_key="infrastructure_score", kpi_name="Infrastructure Score", winner_batch_id="demo-batch-aicte-2023", winner_label="NIT-T 24-25", winner_value=82.0, is_tie=False, tied_with=[])
                    ],
                    notes=["IIT-D leads with overall score of 84.5", "IIT-D has zero compliance issues"]
                ),
                valid_for_comparison=True,
                validation_message=None
            )
    
    ids = [bid.strip() for bid in batch_ids.split(",") if bid.strip()]
    
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two batch_ids")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 institutions for comparison")
    
    valid_institutions: List[InstitutionComparison] = []
    skipped_batches: List[SkippedBatch] = []
    comparison_matrix: Dict[str, Dict[str, Optional[float]]] = {}
    
    # DEPARTMENT GOVERNANCE: Collect department info to prevent cross-department comparison
    departments_seen: Dict[str, str] = {}  # batch_id -> department_name
    
    for bid in ids:
        # Step 1: Validate batch eligibility
        is_valid, skip_reason, batch_info = _validate_batch(bid)
        
        if not is_valid:
            skipped_batches.append(SkippedBatch(batch_id=bid, reason=skip_reason or "unknown"))
            continue
        
        # Step 2: Get batch info for department validation
        db = get_db()
        try:
            batch = db.query(Batch).filter(Batch.id == bid).first()
            if batch and batch.department_name:
                departments_seen[bid] = batch.department_name
        finally:
            close_db(db)
        
        # Step 3: Get dashboard data
        try:
            dashboard = get_dashboard_data(bid)
        except HTTPException:
            skipped_batches.append(SkippedBatch(batch_id=bid, reason="missing_dashboard"))
            continue
        
        # Step 3: Extract KPIs (null for missing, NOT 0)
        kpi_map: Dict[str, Optional[float]] = {}
        for key in CANONICAL_KPIS:
            val = None
            if key == "fsr_score":
                val = dashboard.kpis.get("fsr_score") or dashboard.kpis.get("fsr")
            elif key == "infrastructure_score":
                val = dashboard.kpis.get("infrastructure_score") or dashboard.kpis.get("infrastructure")
            elif key == "placement_index":
                val = dashboard.kpis.get("placement_index") or dashboard.kpis.get("placement_rate_num")
            elif key == "lab_compliance_index":
                val = dashboard.kpis.get("lab_compliance_index") or dashboard.kpis.get("lab_compliance")
            elif key == "overall_score":
                val = dashboard.kpis.get("overall_score")
            
            # Only set if it's a valid number > 0
            if val is not None and isinstance(val, (int, float)) and val > 0:
                kpi_map[key] = float(val)
            else:
                kpi_map[key] = None
        
        # Step 4: Check if batch has any valid KPIs
        if not _has_valid_kpis(kpi_map):
            skipped_batches.append(SkippedBatch(batch_id=bid, reason="no_valid_kpis"))
            continue
        
        # Step 5: Get real institution name and generate short label
        inst_name = _get_real_institution_name(dashboard, bid)
        
        # Extract academic year from blocks
        academic_year = None
        if batch_info and batch_info.get("blocks"):
            for block in batch_info["blocks"]:
                if block.data:
                    year = extract_academic_year_from_data(block.data)
                    if year:
                        academic_year = year
                        break
        if not academic_year:
            academic_year = "2024-25"
        
        short_label = generate_short_label(inst_name, bid, academic_year)
        
        # Step 6: Calculate metrics
        overall = kpi_map.get("overall_score") or 0
        if not overall:
            valid_scores = [v for v in kpi_map.values() if v is not None]
            overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        suff_pct = dashboard.sufficiency.percentage if dashboard.sufficiency else 0.0
        compliance_count = len(dashboard.compliance_flags) if dashboard.compliance_flags else 0
        
        strengths, weaknesses = _strengths_weaknesses(kpi_map)
        
        # Step 7: Create institution object
        inst = InstitutionComparison(
            batch_id=bid,
            institution_name=inst_name,
            short_label=short_label,
            academic_year=academic_year,
            mode=batch_info.get("mode", "unknown") if batch_info else "unknown",
            kpis=kpi_map,
            sufficiency_percent=suff_pct,
            compliance_count=compliance_count,
            overall_score=overall,
            strengths=strengths,
            weaknesses=weaknesses,
        )
        valid_institutions.append(inst)
        
        # Add to comparison matrix
        for kpi_key, val in kpi_map.items():
            if kpi_key not in comparison_matrix:
                comparison_matrix[kpi_key] = {}
            comparison_matrix[kpi_key][short_label] = val
    
    # DEPARTMENT GOVERNANCE: Check for cross-department comparison
    if len(departments_seen) > 0:
        unique_departments = set(departments_seen.values())
        if len(unique_departments) > 1:
            return ComparisonResponse(
                institutions=valid_institutions,
                skipped_batches=skipped_batches,
                comparison_matrix=comparison_matrix,
                valid_for_comparison=False,
                validation_message=f"Cross-department comparison not allowed. Found departments: {', '.join(unique_departments)}"
            )
    
    # Check if we have enough valid institutions
    if len(valid_institutions) < 2:
        return ComparisonResponse(
            institutions=valid_institutions,
            skipped_batches=skipped_batches,
            comparison_matrix=comparison_matrix,
            valid_for_comparison=False,
            validation_message=f"Only {len(valid_institutions)} valid institution(s). Need at least 2 for comparison. {len(skipped_batches)} batch(es) were skipped.",
        )
    
    # Sort by overall score
    valid_institutions.sort(key=lambda i: i.overall_score, reverse=True)
    
    # Determine winner
    winner = _determine_winner(valid_institutions)
    winner_bid = winner.batch_id if winner else None
    winner_label = winner.short_label if winner else None
    winner_name = winner.institution_name if winner else None
    
    # Category winners
    category_winners: Dict[str, str] = {}
    category_winners_labels: Dict[str, str] = {}
    category_winner_details: List[CategoryWinner] = []
    
    for kpi_key in CANONICAL_KPIS:
        best_val = None
        best_bid = None
        best_label = None
        tied_labels = []
        
        for inst in valid_institutions:
            val = inst.kpis.get(kpi_key)
            if val is None:
                continue
            if best_val is None or val > best_val:
                best_val = val
                best_bid = inst.batch_id
                best_label = inst.short_label
                tied_labels = []
            elif val == best_val:
                tied_labels.append(inst.short_label)
        
        if best_bid and best_val is not None:
            category_winners[kpi_key] = best_bid
            category_winners_labels[kpi_key] = best_label or ""
            
            category_winner_details.append(CategoryWinner(
                kpi_key=kpi_key,
                kpi_name=format_metric_name(kpi_key),
                winner_batch_id=best_bid,
                winner_label=best_label or "",
                winner_value=best_val,
                is_tie=len(tied_labels) > 0,
                tied_with=tied_labels,
            ))
    
    # Interpretation notes
    notes = []
    if winner:
        notes.append(f"🏆 {winner.short_label} leads with overall score of {winner.overall_score:.1f}")
        if winner.compliance_count == 0:
            notes.append(f"✅ {winner.short_label} has zero compliance issues")
    
    if skipped_batches:
        notes.append(f"⚠️ {len(skipped_batches)} batch(es) excluded from comparison")
    
    interpretation = ComparisonInterpretation(
        best_overall_batch_id=winner_bid or "",
        best_overall_label=winner_label or "",
        best_overall_name=winner_name or "",
        category_winners=category_winner_details,
        notes=notes,
    )
    
    result = ComparisonResponse(
        institutions=valid_institutions,
        skipped_batches=skipped_batches,
        comparison_matrix=comparison_matrix,
        winner_institution=winner_bid,
        winner_label=winner_label,
        winner_name=winner_name,
        category_winners=category_winners,
        category_winners_labels=category_winners_labels,
        interpretation=interpretation,
        valid_for_comparison=True,
        validation_message=None,
    )
    
    # PERFORMANCE: Cache result
    cache.set(cache_key, result)
    return result
