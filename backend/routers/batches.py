"""
Batch management router - SQLite version
Temporary storage only
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
from schemas.batch import BatchCreate, BatchResponse, BatchListResponse
from config.database import get_db, Batch, close_db
from utils.id_generator import generate_batch_id
from datetime import datetime, timezone
from middleware.auth_middleware import get_current_user
import threading
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=BatchResponse)
def create_batch(
    batch_data: BatchCreate, 
    background_tasks: BackgroundTasks,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Create a new batch - PERFORMANCE: Returns immediately, triggers processing in background.
    No blocking operations - returns in <2 seconds.
    """
    db = get_db()
    
    try:
        # PRODUCTION HARDENING: Department-wise governance validation
        from services.production_guard import ProductionGuard
        
        # DEPARTMENT GOVERNANCE: Enforce exactly one department per batch
        if batch_data.department_name:
            # Department name must be non-empty string
            if not isinstance(batch_data.department_name, str) or not batch_data.department_name.strip():
                raise HTTPException(
                    status_code=400,
                    detail="department_name must be a non-empty string if provided"
                )
        
        # PLATFORM MODEL: Link batch to user - extract early for governance checks
        user_id = user.get("uid") if user else None
        institution_id = user.get("institution_id") if user else None
        department_id = user.get("department_id") if user else None
        
        # DEPARTMENT GOVERNANCE: If user has department_id, enforce it matches
        if user:
            user_department_id = user.get("department_id")
            if user_department_id and department_id and user_department_id != department_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create batches for your own department"
                )
        
        batch_id = generate_batch_id(batch_data.mode.value)
        
        batch = Batch(

            id=batch_id,
            mode=batch_data.mode.value,
            new_university=1 if batch_data.new_university else 0,
            status="created",
            created_at=datetime.now(timezone.utc),
            # PLATFORM MODEL: User ownership
            user_id=user_id,
            institution_id=institution_id,
            department_id=department_id,
            # Department-wise hierarchy (will be extracted from documents if not provided)
            institution_name=batch_data.institution_name,
            department_name=batch_data.department_name,
            academic_year=batch_data.academic_year,
            is_invalid=0  # Start as valid, will be marked invalid if data insufficient
        )
        
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        # PERFORMANCE: Trigger processing in background (non-blocking)
        # Check if files exist before triggering
        from config.database import File
        file_count = db.query(File).filter(File.batch_id == batch_id).count()
        
        if file_count > 0:
            # Files exist - trigger processing in background using BackgroundTasks
            def trigger_processing():
                try:
                    from pipelines.block_processing_pipeline import BlockProcessingPipeline
                    pipeline = BlockProcessingPipeline()
                    # Run in background thread to avoid blocking
                    thread = threading.Thread(
                        target=pipeline.process_batch,
                        args=(batch_id,),
                        daemon=True
                    )
                    thread.start()
                except Exception as e:
                    logger.warning(f"Failed to trigger background processing for {batch_id}: {e}")
            
            # Schedule background processing
            background_tasks.add_task(trigger_processing)
        
        return BatchResponse(
            batch_id=batch_id,
            mode=batch.mode,
            status=batch.status,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.created_at.isoformat(),
            total_documents=file_count,
            processed_documents=0,
            institution_name=None
        )
    except Exception as e:
        db.rollback()
        import traceback
        error_detail = f"Error creating batch: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")
    finally:
        close_db(db)


@router.post("/create", response_model=BatchResponse)
def create_batch_alias(
    batch_data: BatchCreate, 
    background_tasks: BackgroundTasks,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Alias endpoint for POST /api/batches/create to support frontend expectations.
    PERFORMANCE: Fully async - returns immediately, defers heavy work to background.
    """
    try:
        return create_batch(batch_data, background_tasks, user)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error in create_batch_alias: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")


@router.get("/list", response_model=List[BatchResponse])

def list_batches(
    filter: str = None,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    List all batches.
    
    By default, only returns batches with processed_documents > 0 (evidence-driven).
    Only real batches - no demo mode.
    
    Optional filter parameter:
    - filter=all: Return all batches including empty ones
    - filter=valid: Only return completed batches with at least 1 document
    """
    db = get_db()
    
    try:
        from config.database import File, Block
        # PLATFORM MODEL: Filter by user ownership
        query = db.query(Batch)
        
        if user:
            user_id = user.get("uid")
            role = user.get("role", "department")
            
            if role == "institution":
                # Institution users can see all batches (all departments)
                pass
            else:
                # Department users see only their department's batches
                department_id = user.get("department_id")
                if department_id:
                    query = query.filter(Batch.department_id == department_id)
                elif user_id:
                    query = query.filter(Batch.user_id == user_id)
        
        batches = query.order_by(Batch.created_at.desc()).all()
        
        result = []
        for batch in batches:
            file_count = db.query(File).filter(File.batch_id == batch.id).count()
            block_count = db.query(Block).filter(Block.batch_id == batch.id).count()
            
            # Default behavior: filter out batches with 0 processed documents (evidence-driven)
            if filter != "all":
                if file_count == 0 or block_count == 0:
                    continue
            
            # Apply additional filter if specified
            if filter == "valid":
                # Skip batches that are not completed or have 0 documents
                if batch.status != "completed" or file_count == 0:
                    continue
            
            result.append(BatchResponse(
                batch_id=batch.id,
                mode=batch.mode,
                status=batch.status,
                created_at=batch.created_at.isoformat() if batch.created_at else "",
                updated_at=batch.created_at.isoformat() if batch.created_at else "",
                total_documents=file_count if file_count > 0 else (block_count if block_count > 0 else 0),
                processed_documents=file_count if batch.status == "completed" else 0,
                institution_name=batch.institution_name,
                data_source=getattr(batch, 'data_source', 'user') or 'user'
            ))
        
        # NO DEMO BATCHES - System batches are now stored in DB via seeder script
        # Run: python backend/scripts/seed_system_batches.py
        
        return result
    except Exception as e:
        print(f"Error listing batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        close_db(db)


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch(
    batch_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get a specific batch by ID.
    Only real batches - no demo mode.
    """
    db = get_db()
    
    try:
        from config.database import File
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        file_count = db.query(File).filter(File.batch_id == batch_id).count()
        
        return BatchResponse(
            batch_id=batch.id,
            mode=batch.mode,
            status=batch.status,
            created_at=batch.created_at.isoformat() if batch.created_at else "",
            updated_at=batch.created_at.isoformat() if batch.created_at else "",
            total_documents=file_count,
            processed_documents=file_count if batch.status == "completed" else 0,
            institution_name=batch.institution_name
        )
    finally:
        close_db(db)


@router.patch("/{batch_id}", response_model=BatchResponse)

def update_batch(
    batch_id: str,
    batch_data: dict,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Update batch metadata (institution_name, department_name, academic_year).
    PLATFORM MODEL: Allows setting department-wise metadata after batch creation.
    """
    db = get_db()
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # PLATFORM MODEL: Update metadata fields
        if "institution_name" in batch_data:
            batch.institution_name = batch_data["institution_name"]
        if "department_name" in batch_data:
            batch.department_name = batch_data["department_name"]
        if "academic_year" in batch_data:
            batch.academic_year = batch_data["academic_year"]
        
        db.commit()
        db.refresh(batch)
        
        from config.database import File
        file_count = db.query(File).filter(File.batch_id == batch_id).count()
        
        return BatchResponse(
            batch_id=batch.id,
            mode=batch.mode,
            status=batch.status,
            created_at=batch.created_at.isoformat() if batch.created_at else "",
            updated_at=batch.created_at.isoformat() if batch.created_at else "",
            total_documents=file_count,
            processed_documents=file_count if batch.status == "completed" else 0,
            institution_name=batch.institution_name
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating batch {batch_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update batch: {str(e)}")
    finally:
        close_db(db)


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch(
    batch_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """Get batch by ID"""
    db = get_db()
    
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        from config.database import File
        file_count = db.query(File).filter(File.batch_id == batch_id).count()
        
        return BatchResponse(
            batch_id=batch.id,
            mode=batch.mode,
            status=batch.status,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.created_at.isoformat(),
            total_documents=file_count,
            processed_documents=file_count if batch.status == "completed" else 0,
            institution_name=None
        )
    finally:
        close_db(db)

@router.delete("/{batch_id}")
def delete_batch(batch_id: str):
    """Delete batch and associated data"""
    db = get_db()
    
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Delete associated data
        from config.database import Block, File, ComplianceFlag
        db.query(Block).filter(Block.batch_id == batch_id).delete()
        db.query(File).filter(File.batch_id == batch_id).delete()
        db.query(ComplianceFlag).filter(ComplianceFlag.batch_id == batch_id).delete()
        db.delete(batch)
        db.commit()
        
        return {"message": "Batch deleted successfully"}
    finally:
        close_db(db)
