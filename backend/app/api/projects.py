from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from beanie import PydanticObjectId
from app.models.project import ResearchProject
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/", response_model=ResearchProject, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user)
):
    project = ResearchProject(
        title=project_in.title,
        description=project_in.description,
        tags=project_in.tags,
        user_id=current_user.id
    )
    await project.insert()
    return project

@router.get("/", response_model=List[ResearchProject])
async def get_projects(current_user: User = Depends(get_current_user)):
    # Retrieve only current user's projects
    return await ResearchProject.find(
        ResearchProject.user_id == current_user.id
    ).to_list()



@router.get("/{project_id}", response_model=ResearchProject)
async def get_project(
    project_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    project = await ResearchProject.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    if project.user_id and project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    return project

@router.put("/{project_id}", response_model=ResearchProject)
async def update_project(
    project_id: PydanticObjectId,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_user)
):
    project = await ResearchProject.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    if project.user_id and project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    
    update_data = project_in.model_dump(exclude_unset=True)
    await project.update_project(**update_data)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    project = await ResearchProject.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    if project.user_id and project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    await project.delete()
    return None

