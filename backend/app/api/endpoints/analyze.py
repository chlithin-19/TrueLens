import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db.session import get_db
from app.models.analysis import Analysis
from app.schemas.analysis import AnalysisCreate, AnalysisResponse, DashboardStats, ClaimVerify
from app.core.auth import get_current_user
from app.models.user import User
from app.core.ingestion import ingest_from_url, ingest_from_pdf
from app.models.article import Article
from app.services import analysis_pipeline, embedding_service



router = APIRouter()

@router.post("/", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_url(
    payload: AnalysisCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    url = payload.url
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    # 1. Run real URL ingestion
    try:
        article_data = ingest_from_url(url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to ingest content from URL: {str(e)}"
        )
    
    # 2. Store Article record in PostgreSQL
    article = Article(
        title=article_data["title"],
        content=article_data["content"],
        author=article_data["author"],
        publication=article_data["publication"],
        published_date=article_data["published_date"],
        url=url,
        user_id=current_user.id
    )
    db.add(article)
    await db.flush() # Retrieve generated UUID
    
    # 3. Process through AI Pipeline
    pipeline_result = await analysis_pipeline.analyze(article_data, article.id)
    
    # 4. Store Analysis result
    analysis = Analysis(
        id=str(uuid.uuid4()),
        url=url,
        title=pipeline_result.title,
        author=pipeline_result.author,
        publication=pipeline_result.publication,
        published_date=pipeline_result.published_date,
        trust_score=pipeline_result.trust_score,
        bias_rating=pipeline_result.bias_rating,
        sentiment_tone=pipeline_result.sentiment_tone,
        sentiment_score=pipeline_result.sentiment_score,
        is_clickbait=pipeline_result.is_clickbait,
        is_sensational=pipeline_result.is_sensational,
        is_verified_author=pipeline_result.is_verified_author,
        summary=pipeline_result.summary,
        claims=pipeline_result.claims,
        emotion=pipeline_result.emotion,
        propaganda_score=pipeline_result.propaganda_score,
        propaganda_techniques=pipeline_result.propaganda_techniques,
        missing_perspectives=pipeline_result.missing_perspectives,
        embedding_id=pipeline_result.embedding_id,
        user_id=current_user.id,
        article_id=article.id
    )
    
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis

@router.post("/upload", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_file(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = file.filename
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF file uploads are currently supported.")
        
    # 1. Run real PDF ingestion
    try:
        file_bytes = await file.read()
        article_data = ingest_from_pdf(file_bytes, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse PDF document: {str(e)}"
        )
        
    # 2. Store Article record in PostgreSQL
    article = Article(
        title=article_data["title"],
        content=article_data["content"],
        author=article_data["author"],
        publication=article_data["publication"],
        published_date=article_data["published_date"],
        filename=filename,
        user_id=current_user.id
    )
    db.add(article)
    await db.flush()
    
    # 3. Process through AI Pipeline
    pipeline_result = await analysis_pipeline.analyze(article_data, article.id)
    
    # 4. Store Analysis record
    analysis = Analysis(
        id=str(uuid.uuid4()),
        filename=filename,
        title=pipeline_result.title,
        author=pipeline_result.author,
        publication=pipeline_result.publication,
        published_date=pipeline_result.published_date,
        trust_score=pipeline_result.trust_score,
        bias_rating=pipeline_result.bias_rating,
        sentiment_tone=pipeline_result.sentiment_tone,
        sentiment_score=pipeline_result.sentiment_score,
        is_clickbait=pipeline_result.is_clickbait,
        is_sensational=pipeline_result.is_sensational,
        is_verified_author=pipeline_result.is_verified_author,
        summary=pipeline_result.summary,
        claims=pipeline_result.claims,
        emotion=pipeline_result.emotion,
        propaganda_score=pipeline_result.propaganda_score,
        propaganda_techniques=pipeline_result.propaganda_techniques,
        missing_perspectives=pipeline_result.missing_perspectives,
        embedding_id=pipeline_result.embedding_id,
        user_id=current_user.id,
        article_id=article.id
    )
    
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis

@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses(
    limit: int = 50,
    search: str = None,
    sort_by: str = "created_at",
    order: str = "desc",
    is_bookmarked: bool = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Analysis).where(Analysis.user_id == current_user.id)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Analysis.title.ilike(search_term)) | 
            (Analysis.publication.ilike(search_term)) |
            (Analysis.summary.ilike(search_term))
        )
        
    if is_bookmarked is not None:
        query = query.where(Analysis.is_bookmarked == is_bookmarked)
        
    # Handling sorting
    if sort_by == "trust_score":
        order_col = Analysis.trust_score
    else:
        order_col = Analysis.created_at
        
    if order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
        
    query = query.limit(limit)
    result = await db.execute(query)
    analyses = result.scalars().all()
    
    return analyses

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Calculate stats from DB specifically for the logged-in user
    result_count = await db.execute(
        select(func.count(Analysis.id)).where(Analysis.user_id == current_user.id)
    )
    total_analyzed = result_count.scalar() or 0
    
    result_avg = await db.execute(
        select(func.avg(Analysis.trust_score)).where(Analysis.user_id == current_user.id)
    )
    avg_score = result_avg.scalar()
    avg_trust_score = int(round(avg_score)) if avg_score is not None else 0
    
    # Calculate total verified claims for the user
    # Note: SQLite/PostgreSQL JSON querying can be complex. For simplicity and DB agnosticism, 
    # we'll fetch the claims for the user and count them in python if it's not a huge dataset,
    # but a better approach for large scale is a separate Claims table.
    # Since this is a lightweight prototype, we'll fetch analyses for the user and count.
    all_user_analyses_result = await db.execute(select(Analysis.claims).where(Analysis.user_id == current_user.id))
    all_claims = all_user_analyses_result.scalars().all()
    verified_facts = 0
    for claims_list in all_claims:
        if isinstance(claims_list, list):
            verified_facts += sum(1 for c in claims_list if isinstance(c, dict) and c.get("status") == "Verified")
            
    # Count bookmarked
    result_bookmarked = await db.execute(
        select(func.count(Analysis.id)).where((Analysis.user_id == current_user.id) & (Analysis.is_bookmarked == True))
    )
    saved_reports = result_bookmarked.scalar() or 0
    
    stats = DashboardStats(
        total_analyzed=total_analyzed,
        verified_facts=verified_facts,
        avg_trust_score=avg_trust_score,
        saved_reports=saved_reports
    )
    return stats

@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404, 
            detail=f"Analysis report with ID {analysis_id} not found."
        )
        
    # Enforce security scope: only allow access to user's own reports or public reports
    if analysis.user_id and analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view this analysis report."
        )
        
    # Fetch similar articles using embedding_service
    similar_articles = []
    if analysis.content:
        # We need the article's text, which is accessed via the relationship analysis.article.content (already a property on the model)
        # However, to avoid lazy loading issues, we can check if it exists or use the summary if content is not available.
        search_text = analysis.content if analysis.content else analysis.summary
        if search_text:
            results = embedding_service.search_similar(search_text, top_k=6)
            for res in results:
                metadata = res.get("metadata", {})
                # Skip the exact same article
                if metadata.get("article_id") == analysis.article_id:
                    continue
                    
                similar_articles.append({
                    "id": res.get("id"),
                    "title": metadata.get("title", "Unknown Title"),
                    "author": metadata.get("author", "Unknown"),
                    "publication": metadata.get("publication", "Unknown"),
                    "url": metadata.get("url"),
                    "distance": res.get("distance")
                })
                if len(similar_articles) == 5:
                    break
    
    # We must construct a dict or modify the Pydantic model response
    # Because similar_articles is not a Column, it's easier to convert the SQLAlchemy object to dict and update it.
    analysis_dict = {c.name: getattr(analysis, c.name) for c.__class__ in analysis.__table__.columns} if hasattr(analysis, "__table__") else vars(analysis).copy()
    if "_sa_instance_state" in analysis_dict:
        del analysis_dict["_sa_instance_state"]
        
    analysis_dict = {
        "id": analysis.id,
        "url": analysis.url,
        "filename": analysis.filename,
        "title": analysis.title,
        "author": analysis.author,
        "publication": analysis.publication,
        "published_date": analysis.published_date,
        "trust_score": analysis.trust_score,
        "bias_rating": analysis.bias_rating,
        "sentiment_tone": analysis.sentiment_tone,
        "sentiment_score": analysis.sentiment_score,
        "is_clickbait": analysis.is_clickbait,
        "is_sensational": analysis.is_sensational,
        "is_verified_author": analysis.is_verified_author,
        "summary": analysis.summary,
        "content": analysis.content,
        "claims": analysis.claims,
        "emotion": analysis.emotion,
        "propaganda_score": analysis.propaganda_score,
        "propaganda_techniques": analysis.propaganda_techniques,
        "missing_perspectives": analysis.missing_perspectives,
        "embedding_id": analysis.embedding_id,
        "is_bookmarked": analysis.is_bookmarked,
        "created_at": analysis.created_at,
        "similar_articles": similar_articles
    }
    
    return analysis_dict

@router.post("/{analysis_id}/bookmark", response_model=dict)
async def toggle_bookmark(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where((Analysis.id == analysis_id) & (Analysis.user_id == current_user.id))
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    analysis.is_bookmarked = not analysis.is_bookmarked
    await db.commit()
    
    return {"status": "success", "is_bookmarked": analysis.is_bookmarked}

@router.delete("/{analysis_id}", response_model=dict)
async def delete_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where((Analysis.id == analysis_id) & (Analysis.user_id == current_user.id))
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    await db.delete(analysis)
    await db.commit()
    
    return {"status": "success", "message": "Analysis deleted"}

