from fastapi import FastAPI, Form, File, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
from config import db, bucket, API_URL
from datetime import datetime, timedelta

import requests
import json
import base64
import os
import io
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # use ["*"] to allow all origins (not recommended in prod)
    allow_credentials=True,
    allow_methods=["*"],  # or specify ["GET", "POST", ...]
    allow_headers=["*"],
)
class UserProfile(BaseModel):
    userId: str
    timestamp: str
    userProfile: dict
    metadata: dict

  
feature_api_config = {
    "analyze-ad": {
        "url": f"{API_URL}analyze-ad",  
    },
    "brand-compliance": {
        "url": f"{API_URL}brand-compliance",
    },
    "channel-compliance": {
        "url": f"{API_URL}channel-compliance",
    },
    "metaphor-analysis": {
        "url": f"{API_URL}metaphor-analysis",
    },
    "comprehensive-analysis": {
        "url": f"{API_URL}comprehensive-analysis",
    },
}
 
@app.post("/save-user-profile")
async def save_user_profile(profile: UserProfile):
    try:
        # Create unique ID for the user
        user_id = str(uuid.uuid4())
 
        # Prepare data
        data = profile.dict()
        data["user_id"] = user_id
 
        # Save to Firebase Firestore
        db.collection("user_profiles").document(user_id).set(data)
        print('saveuser')
        return {"message": "User profile saved successfully", "user_id": user_id}
   
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.get("/get-user-profile/{user_id}")
async def get_user_profile(user_id: str):
    try:
        # Fetch document by ID from Firestore
        doc_ref = db.collection("userProfileDetails").document(user_id)
        doc = doc_ref.get()
        print('getuser')
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile_data = doc.to_dict()
        
        # Note: Removed hardcoded max_ads_per_month correction logic
        # The database now stores the correct values for topup/upgrade scenarios
        # where users may have combined plans (e.g., Pro + Pro = 22 ads/month)

        return profile_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.post("/UserProfileDetails")
async def post_user_profile(profile: UserProfile):
    try:
       # user_id = str(uuid.uuid4())
        data = profile.dict()
        user_id = data["userId"]
        print('postuser')
        db.collection("userProfileDetails").document(user_id).set(data)
        return {"message": "User profile saved successfully", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/updateUserProfileDetails/{user_id}")
async def update_user_profile_details(user_id: str, request: Request):
    """Merge arbitrary updates into userProfileDetails. Accepts JSON { updates: {...}, timestamp?: str }"""
    try:
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        updates = payload.get("updates", {})
        if not isinstance(updates, dict):
            raise HTTPException(status_code=400, detail="'updates' must be an object")

        # Always bump updatedAt
        updates.setdefault("updatedAt", datetime.utcnow().isoformat())

        profile_ref = db.collection("userProfileDetails").document(user_id)
        profile_ref.set(updates, merge=True)
        return {"message": "User profile updated", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.post("/branddata-form")
async def receive_brand_form(
    request: Request,
    userId: str = Form(...),
    timestamp: str = Form(...),
    brandName: str = Form(...),
    tagline: str = Form(...),
    brandDescription: str = Form(...),
    industryCategory: str = Form(...),
    targetAudience: str = Form(...),
    primaryColor: str = Form(...),
    secondaryColor: str = Form(...),
    accentColor: str = Form(...),
    colorPalette: str = Form(...),
    toneOfVoice: str = Form(...),
    customTone: str = Form(...),
    communicationStyle: str = Form(...),
    brandVoice: str = Form(...),
    keyMessages: str = Form(...),
    isComplete: bool = Form(...),
    completionPercentage: int = Form(...),
    lastUpdated: str = Form(...),
    dataVersion: float = Form(...),
    source: str = Form(...),
    apiEndpoint: str = Form(...),
    submissionSource: str = Form(...),
    systemMetadata: str = Form(...),
    logoFiles: Optional[list[UploadFile]] = File(None),
    logoMetadata: Optional[list[str]] = Form(None)
):
    try:
        brand_id = str(uuid.uuid4())
        
        # Allowed file types
        ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
        ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
        
        media_info_list = []
        
        # Sanitize brand name for file path (remove special characters)
        sanitized_brand_name = "".join(c for c in brandName if c.isalnum() or c in (' ', '-', '_')).rstrip()
        sanitized_brand_name = sanitized_brand_name.replace(' ', '_')
        
        print(f"📁 Brand name: {brandName}")
        print(f"📁 Sanitized brand name: {sanitized_brand_name}")
        
        # Process logo files provided as arrays
        if logoFiles:
            for i, logo_file in enumerate(logoFiles):
                if logo_file.content_type not in ALLOWED_IMAGE_TYPES:
                    raise HTTPException(status_code=400, detail=f"Invalid file type for logo: {logo_file.content_type}")
                if getattr(logo_file, "size", None) and logo_file.size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail=f"File too large: {logo_file.filename}")
                file_ext = os.path.splitext(logo_file.filename)[1]
                media_id = str(uuid.uuid4())
                storage_filename = f"{userId}/{sanitized_brand_name}/{brand_id}/logo/{media_id}{file_ext}"
                print(f"📁 Uploading logo: {storage_filename}")
                blob = bucket.blob(storage_filename)
                blob.upload_from_file(logo_file.file, content_type=logo_file.content_type)
                #media_url = blob.generate_signed_url(expiration=3600 * 24 * 7)
                media_url = blob.generate_signed_url(
                version="v4",                # use v4 signed URLs
                expiration=timedelta(days=7), # 7 days from now
                method="GET"                  # HTTP method allowed
                )
                metadata = logoMetadata[i] if logoMetadata and i < len(logoMetadata) else ""
                media_info_list.append({
                    "fileId": media_id,
                    "filename": logo_file.filename,
                    "contentType": logo_file.content_type,
                    "fileSize": getattr(logo_file, "size", None),
                    "url": media_url,
                    "storagePath": storage_filename,
                    "mediaType": "logo",
                    "metadata": metadata,
                    "uploadTimestamp": datetime.utcnow().isoformat()
                })

        # Also support enumerated fields: logo_0, logo_1, ... using logoCount
        try:
            form = await request.form()
        except Exception:
            form = None
        if form is not None:
            raw_logo_count = form.get("logoCount")
            try:
                count = int(raw_logo_count) if raw_logo_count is not None else 0
            except ValueError:
                count = 0
            for i in range(count):
                field_name = f"logo_{i}"
                if field_name not in form:
                    continue
                logo_file = form.get(field_name)
                if not logo_file:
                    continue
                # Starlette returns UploadFile for file fields
                if getattr(logo_file, "content_type", None) not in ALLOWED_IMAGE_TYPES:
                    raise HTTPException(status_code=400, detail=f"Invalid file type for logo: {getattr(logo_file, 'content_type', 'unknown')}")
                size_attr = getattr(logo_file, "size", None)
                if size_attr and size_attr > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail=f"File too large: {logo_file.filename}")
                file_ext = os.path.splitext(logo_file.filename)[1]
                media_id = str(uuid.uuid4())
                storage_filename = f"{userId}/{sanitized_brand_name}/{brand_id}/logo/{media_id}{file_ext}"
                print(f"📁 Uploading logo (enum): {storage_filename}")
                blob = bucket.blob(storage_filename)
                blob.upload_from_file(logo_file.file, content_type=logo_file.content_type)
                #media_url = blob.generate_signed_url(expiration=3600 * 24 * 7)
                media_url = blob.generate_signed_url(
                version="v4",                # use v4 signed URLs
                expiration=timedelta(days=7), # 7 days from now
                method="GET"                  # HTTP method allowed
                )
                # Metadata key typo tolerant: logo_0_metadata or log_0_metadata
                meta_key = f"logo_{i}_metadata"
                alt_meta_key = f"log_{i}_metadata"
                metadata = form.get(meta_key) or form.get(alt_meta_key) or ""
                media_info_list.append({
                    "fileId": media_id,
                    "filename": logo_file.filename,
                    "contentType": logo_file.content_type,
                    "fileSize": size_attr,
                    "url": media_url,
                    "storagePath": storage_filename,
                    "mediaType": "logo",
                    "metadata": metadata,
                    "uploadTimestamp": datetime.utcnow().isoformat()
                })
        


        data = {
            "userId": userId,
            "timestamp": timestamp,
            "brandName": brandName,
            "tagline": tagline,
            "brandDescription": brandDescription,
            "industryCategory": industryCategory,
            "targetAudience": targetAudience,
            "primaryColor": primaryColor,
            "secondaryColor": secondaryColor,
            "accentColor": accentColor,
            "colorPalette": colorPalette,
            "toneOfVoice": toneOfVoice,
            "customTone": customTone,
            "communicationStyle": communicationStyle,
            "brandVoice": brandVoice,
            "keyMessages": keyMessages,
            "isComplete": isComplete,
            "completionPercentage": completionPercentage,
            "lastUpdated": lastUpdated,
            "dataVersion": dataVersion,
            "source": source,
            "apiEndpoint": apiEndpoint,
            "submissionSource": submissionSource,
            "systemMetadata": systemMetadata,
            "mediaFiles": media_info_list,
            "mediaCount": len(media_info_list),
            "brandId": brand_id
        }

        # Store in Firestore
        db.collection("brandData").document(brand_id).set(data)

        return {
            "message": "Brand data saved successfully", 
            "brand_id": brand_id,
            "logo_count": len(media_info_list),
            "logo_files": media_info_list
        }

    except Exception as e:
        print("Error saving brand data:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save-plan-selection")
async def save_plan_selection(
    userId: str = Form(...),
    planId: str = Form(...),
    planName: str = Form(...),
    paymentId: str = Form(...),
    paymentStatus: str = Form(...),
    subscriptionType: str = Form(...),
    subscriptionStartDate: str = Form(...),
    subscriptionEndDate: str = Form(...),
    totalPrice: float = Form(...),
    basePrice: float = Form(...),
    additionalAdPrice4: float = Form(...),
    totalAds: int = Form(...),
    validityDays: int = Form(...),
    isActive: bool = Form(...),
    selectedFeatures: list[str] = Form(...),
    createdAt: str = Form(...),
    updatedAt: str = Form(...),
    max_ads_per_month: int = Form(...)
            
):
    try:
        doc_id = userId
        
        # selectedFeatures may arrive as an array, or as a single comma-separated string inside an array
        features_list = selectedFeatures or []
        if len(features_list) == 1 and "," in features_list[0]:
            features_list = [item.strip().strip('"\'') for item in features_list[0].split(',') if item.strip()]
        
        # Build indexed map: {"0": feature0, "1": feature1, ...}
        features_indexed = {str(i): feature for i, feature in enumerate(features_list)}
        
        plan_data = {
            "userId": userId,
            "planId": planId,
            "planName": planName,
            "paymentId": paymentId,
            "paymentStatus": paymentStatus,
            "subscriptionType": subscriptionType,
            "subscriptionStartDate": subscriptionStartDate,
            "subscriptionEndDate": subscriptionEndDate,
            "totalPrice": totalPrice,
            "basePrice": basePrice,
            "additionalAdPrice4": additionalAdPrice4,
            "totalAds": totalAds,
            "validityDays": validityDays,
            "isActive": isActive,
            "selectedFeatures": features_list,
            #"selectedFeaturesIndexed": features_indexed,
            "createdAt": createdAt,
            "updatedAt": updatedAt,
            "max_ads_per_month": max_ads_per_month,
            "adsUsed": 0
        }
        
        db.collection("PlanSelectionDetails").document(doc_id).set(plan_data)

        # Also upsert subscription into user profile so frontend can read it
        try:
            subscription = {
                "planType": planId,
                "planName": planName,
                "features": features_list,
                "adQuota": totalAds,
                "totalPrice": totalPrice,
                "basePrice": basePrice,
                "validityDays": validityDays,
                "subscriptionStartDate": subscriptionStartDate,
                "subscriptionEndDate": subscriptionEndDate,
                "status": "active" if isActive else "inactive",
                "adsUsed": 0,
                "max_ads_per_month": max_ads_per_month,
                "paymentStatus": paymentStatus,
                "paymentId": paymentId,
                "subscriptionType": subscriptionType,
                "updatedAt": updatedAt,
            }
            profile_ref = db.collection("userProfileDetails").document(userId)
            profile_ref.set({
                "userId": userId,
                "subscription": subscription,
                "updatedAt": updatedAt,
            }, merge=True)
        except Exception as e:
            # Do not fail the request if profile upsert fails; log instead
            print(f"Warning: could not upsert subscription into user profile: {e}")

        return {"message": "Plan selection saved", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving plan: {str(e)}")



   
@app.post("/postAnalysisDetailsFormData")
async def post_analysis_details_form_data(
    userId: str = Form(...),
    brandId: str = Form(...),
    timestamp: str = Form(...),
    messageIntent: str = Form(...),
    funnelStage: str = Form(...),
    channels: str = Form(...),   # channel compliance
    source: str = Form(...),
    clientId: str = Form(...),
    artifacts: str = Form(...),
    adTitle: str = Form(""),     # Ad title for display in Libraries
    mediaFile: UploadFile = File(...)
):
    """
    Main endpoint for AI analysis of media files.
    
    This endpoint:
    1. Validates user plan and monthly limits
    2. Accepts media files (images/videos) and optional logo files
    3. Uploads files to Google Cloud Storage
    4. Calls multiple AI models for analysis
    5. Stores results in user_analysis collection
    6. Updates plan usage statistics
    7. Returns comprehensive analysis results
    
    Parameters:
    - userId: User identifier
    - brandId: Brand identifier (required)
    - mediaFile: Main media file to analyze (required)
    - Other parameters for context and analysis configuration
    
    Returns:
    - JSON response with analysis results from all AI models
    - Success/failure statistics
    - Media and brand information
    """
    try:
        # Debug: Log received parameters
        print(f"🔍 DEBUG: Received adTitle: '{adTitle}'")
        print(f"🔍 DEBUG: Received messageIntent: '{messageIntent}'")
        print(f"🔍 DEBUG: Received funnelStage: '{funnelStage}'")
        
        artifact_id = str(uuid.uuid4())
        
        # Input validation
        if not mediaFile or mediaFile.filename == "":
            raise HTTPException(status_code=400, detail="Media file is required")
        
        if not userId or userId.strip() == "":
            raise HTTPException(status_code=400, detail="User ID is required")
        
        if not brandId or brandId.strip() == "":
            raise HTTPException(status_code=400, detail="Brand ID is required")
        

        
        # ===== PLAN VALIDATION AND MONTHLY RESET LOGIC =====
        try:
            # Get user's plan details
            plan_doc = db.collection("PlanSelectionDetails").document(userId).get()
            if not plan_doc.exists:
                raise HTTPException(status_code=404, detail="User plan not found. Please select a plan first.")
            
            plan_data = plan_doc.to_dict()
            max_ads_per_month = plan_data.get("max_ads_per_month", 0)
            ads_used = plan_data.get("adsUsed", 0)
            total_ads = plan_data.get("totalAds", 0)
            last_usage_date = plan_data.get("lastUsageDate")
            
            # Check if we need to reset monthly usage (new month)
            current_date = datetime.utcnow()
            print(f"🔍 Monthly usage check - Current date: {current_date}, Last usage: {last_usage_date}")
            
            if last_usage_date:
                try:
                    last_usage = datetime.fromisoformat(last_usage_date.replace("Z", ""))
                    print(f"🔍 Parsed dates - Current: {current_date.year}-{current_date.month:02d}, Last: {last_usage.year}-{last_usage.month:02d}")
                    
                    # Reset if it's a new month
                    if (current_date.year != last_usage.year or current_date.month != last_usage.month):
                        print(f"🔄 Monthly reset triggered: {last_usage.month}/{last_usage.year} -> {current_date.month}/{current_date.year}")
                        print(f"🔍 BEFORE reset - ads_used: {ads_used}")
                        ads_used = 0
                        print(f"🔍 AFTER reset - ads_used: {ads_used}")
                    else:
                        print(f"✅ Same month - preserving ads_used: {ads_used}")
                except Exception as e:
                    print(f"⚠️ Warning: Could not parse last usage date: {e}")
                    print(f"🔍 Defaulting ads_used to 0 due to parse error")
                    ads_used = 0
            else:
                print(f"🔍 No last usage date - keeping ads_used: {ads_used}")
            
            # Check monthly limit
            if ads_used >= max_ads_per_month:
                raise HTTPException(
                    status_code=429, 
                    detail=f"Maximum monthly limit reached ({max_ads_per_month} ads). Please wait until next month or upgrade your plan."
                )
            
            # Check total ads remaining
            if total_ads <= 0:
                raise HTTPException(
                    status_code=400, 
                    detail="No ads remaining in your plan. Please purchase more ads or upgrade your plan."
                )
            
            print(f"✅ Plan validation passed: {ads_used}/{max_ads_per_month} monthly, {total_ads} total remaining")
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error during plan validation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error validating user plan: {str(e)}")
        
        # Debug: Print received values
        print(f"🔍 DEBUG: Received channels: '{channels}'")
        print(f"🔍 DEBUG: Received artifacts: '{artifacts}'")
        print(f"🔍 DEBUG: Media file: {mediaFile.filename} ({mediaFile.content_type})")
        print(f"🔍 DEBUG: Logo will be fetched from brand data")
        
        # Safely parse channels JSON with multiple format support
        channels_list = []
        try:
            if channels and channels.strip():
                # Try to parse as JSON first
                try:
                    channels_list = json.loads(channels)
                except json.JSONDecodeError:
                    # If JSON fails, try comma-separated string
                    if "," in channels:
                        channels_list = [channel.strip() for channel in channels.split(",") if channel.strip()]
                    else:
                        # Single value
                        channels_list = [channels.strip()] if channels.strip() else []
                
                # Ensure it's a list
                if not isinstance(channels_list, list):
                    channels_list = [channels_list] if channels_list else []
                
                print(f"✅ DEBUG: Parsed channels_list: {channels_list}")
            else:
                print(f"⚠️ Channels is empty or None")
                channels_list = []
        except Exception as e:
            print(f"Warning: Error parsing channels '{channels}': {e}")
            channels_list = []
        
        # Safely parse artifacts JSON with multiple format support
        artifacts_data = {}
        try:
            if artifacts and artifacts.strip():
                # Try to parse as JSON first
                try:
                    artifacts_data = json.loads(artifacts)
                except json.JSONDecodeError:
                    # If JSON fails, try to create a simple object
                    print(f"Warning: Invalid artifacts JSON: {artifacts}, using empty object")
                    artifacts_data = {}
                
                # Ensure it's a dict
                if not isinstance(artifacts_data, dict):
                    artifacts_data = {}
                
                print(f"✅ DEBUG: Parsed artifacts_data: {artifacts_data}")
            else:
                print(f"⚠️ Artifacts is empty or None")
                artifacts_data = {}
        except Exception as e:
            print(f"Warning: Error parsing artifacts '{artifacts}': {e}")
            artifacts_data = {}
        
        # Validate and provide defaults for required fields
        if not messageIntent or messageIntent.strip() == "":
            messageIntent = "string"
            print(f"⚠️ messageIntent was empty, using default: {messageIntent}")
        
        if not funnelStage or funnelStage.strip() == "":
            funnelStage = "string"
            print(f"⚠️ funnelStage was empty, using default: {funnelStage}")
        
        # Get brand data using specific brandId from brandData collection
        brand_name = "Unknown Brand"
        brand_logo = "default_logo.png"
        tone_of_voice = "Professional and friendly"
        brand_colours = "#FF0000,#00FF00,#0000FF"
        logo_data = None
        
        try:
            # Get specific brand document by brandId
            brand_doc = db.collection("brandData").document(brandId).get()
            
            if brand_doc.exists:
                brand_data = brand_doc.to_dict()
                
                # Verify the brand belongs to the user
                if brand_data.get("userId") != userId:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Brand ID {brandId} does not belong to user {userId}"
                    )
                
                brand_name = brand_data.get("brandName", "Unknown Brand")
                brand_logo = brand_data.get("brandLogo", "default_logo.png")
                tone_of_voice = brand_data.get("toneOfVoice", "Professional and friendly")
                brand_colours = brand_data.get("colorPalette", "#FF0000,#00FF00,#0000FF")
                
                # Extract logo information from mediaFiles array
                media_files = brand_data.get("mediaFiles", [])
                for media_file in media_files:
                    if media_file.get("mediaType") == "logo":
                        logo_data = {
                            "logoUrl": media_file.get("url"),
                            "logoType": media_file.get("contentType"),
                            "logoStoragePath": media_file.get("storagePath"),
                            "logoCategory": media_file.get("mediaType"),
                            "logoFilename": media_file.get("filename"),
                            "logoFileSize": media_file.get("fileSize"),
                            "logo_artifact_id": media_file.get("fileId")
                        }
                        print(f"✅ Found logo in brand data: {logo_data['logoFilename']}")
                        break
                
                print(f"✅ Found brand data: {brand_name}, ID: {brandId}")
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Brand with ID {brandId} not found"
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Error getting brand data: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error fetching brand data: {str(e)}"
            )
        
        # Define allowed file types (same as in other endpoints)
        ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
        ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
        
        # Validate media file type
        if mediaFile.content_type not in ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid media file type: {mediaFile.content_type}. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES)}"
            )
        
        # Determine media type based on content type using predefined lists
        media_type = "image"  # default
        content_type = mediaFile.content_type
        
        if content_type in ALLOWED_VIDEO_TYPES:
            media_type = "video"
        elif "logo" in mediaFile.filename.lower() or "logo" in content_type.lower():
            media_type = "logo"
        elif content_type in ALLOWED_IMAGE_TYPES:
            media_type = "image"
        
        # Create storage path with structure: user_id - brand_name - brandId - media_type
        file_ext = os.path.splitext(mediaFile.filename)[1]
        storage_path = f"{userId}/{brand_name}/{brandId}/{media_type}/{artifact_id}{file_ext}"
        storage_filename = storage_path
        
        print(f"📁 Storage path: {storage_path}")
        print(f"📁 Media type: {media_type}")
        print(f"📁 Content type: {content_type}")
        
        # Upload to GCS with the new path structure
        blob = bucket.blob(storage_filename)
        blob.upload_from_file(mediaFile.file, content_type=mediaFile.content_type)
        #media_url = blob.generate_signed_url(expiration=3600 * 24 * 7)
        media_url = blob.generate_signed_url(
                version="v4",                # use v4 signed URLs
                expiration=timedelta(days=7), # 7 days from now
                method="GET"                  # HTTP method allowed
            )
        
        # Logo data is fetched from brandData collection above
        # No need to process uploaded logo file since we get it from brand data
 

 
        # Use only comprehensive-analysis for AI results
        selected_features = ["comprehensive-analysis"]
        print("Using comprehensive-analysis model for AI results")
 
        # Brand data is already fetched above using userId
        # Use the values we got from the brandData collection query
 
        results = {}
 
        # Process comprehensive-analysis only
        feature = "comprehensive-analysis"
        feature_config = feature_api_config.get(feature)
 
        if not feature_config:
            results[feature] = {"error": "No API configured for comprehensive-analysis"}
        else:
            try:
                print(f'🤖 Processing comprehensive-analysis')
                url = feature_config["url"]
 
                # Create a fresh file object for the request
                mediaFile.file.seek(0)
                file_content = mediaFile.file.read()
                file_obj = io.BytesIO(file_content)
 
                # Map channels to valid platform names
                platform_mapping = {
                    "facebook": "Facebook",
                    "instagram": "Instagram", 
                    "google ads": "Google Ads",
                    "youtube": "YouTube",
                    "tiktok": "TikTok"
                }
                comp_platforms = []
                print(f"🔍 DEBUG: Channels list: {channels_list}")
                for channel in channels_list:
                    if channel.lower() in platform_mapping:
                        comp_platforms.append(platform_mapping[channel.lower()])
                
                # Use only the platforms provided in the request, no defaults
                if not comp_platforms:
                    print(f"⚠️ No valid platforms found in channels: {channels_list}")
                    comp_platforms = []  # Empty list instead of defaults
                
                # Prepare form data for comprehensive analysis
                form_data = {
                    "ad_description": messageIntent,
                    "user_ad_type": funnelStage,
                    "brand_colors": brand_colours,
                    "tone_of_voice": tone_of_voice,
                    "platforms": ",".join(comp_platforms)
                }
                files = {
                    "file": (mediaFile.filename, file_obj, mediaFile.content_type)
                }
                
                # Add logo from brand data if available
                if logo_data and logo_data.get("logoUrl"):
                    form_data["logo_url"] = logo_data["logoUrl"]
 
                print(f"🤖 Calling comprehensive-analysis at {url}")
                print(f"📤 Form data: {form_data}")
                response = requests.post(url, data=form_data, files=files, timeout=1200)
 
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        results[feature] = {"success": True, "data": response_data}
                        print(f"✅ comprehensive-analysis: Success")
                    except json.JSONDecodeError:
                        results[feature] = {"success": True, "data": response.text}
                        print(f"✅ comprehensive-analysis: Success (non-JSON response)")
                else:
                    results[feature] = {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text
                    }
                    print(f"❌ comprehensive-analysis: Failed - {response.status_code}")
 
            except requests.exceptions.RequestException as e:
                results[feature] = {"success": False, "error": str(e)}
                print(f"❌ comprehensive-analysis: Exception - {str(e)}")
 
        # ===== STORE ANALYSIS RESULTS AND UPDATE PLAN USAGE ONLY ON SUCCESS =====
        try:
            # Calculate success statistics first
            successful_models = [feature for feature, result in results.items() if result.get('success', False)]
            failed_models = [feature for feature, result in results.items() if not result.get('success', False)]
            
            # Check if we have at least one successful model
            if len(successful_models) == 0:
                print(f"❌ No successful models found. Skipping plan usage update.")
                raise Exception("No successful AI models completed. Analysis failed.")
            
            # Check if we have a reasonable success rate (at least 50% of requested models)
            success_rate = len(successful_models) / len(selected_features) if selected_features else 0
            if success_rate < 0.5:
                print(f"⚠️ Low success rate ({success_rate:.1%}). Only {len(successful_models)}/{len(selected_features)} models succeeded.")
                # Still proceed but log the warning
            
            # Only update plan usage if we have successful analysis results
            new_ads_used = ads_used + 1
            new_total_ads = total_ads - 1
            
            plan_updates = {
                "adsUsed": new_ads_used,
                "totalAds": new_total_ads,
                "lastUsageDate": current_date.isoformat() + "Z",
                "updatedAt": current_date.isoformat() + "Z"
            }
            
            # Update the plan document
            db.collection("PlanSelectionDetails").document(userId).update(plan_updates)
            print(f"✅ Plan usage updated: {new_ads_used}/{max_ads_per_month} monthly, {new_total_ads} total remaining")
            
            # SYNC: Also update the user profile subscription data so frontend shows correct data
            try:
                profile_ref = db.collection("userProfileDetails").document(userId)
                profile_ref.update({
                    "subscription.adsUsed": new_ads_used,
                    "subscription.adQuota": new_total_ads,  # FIX: Use decremented new_total_ads for correct frontend display
                    "subscription.max_ads_per_month": max_ads_per_month,
                    "subscription.updatedAt": current_date.isoformat() + "Z",
                    "updatedAt": current_date.isoformat() + "Z"
                })
                print(f"✅ User profile subscription synced: {new_ads_used} ads used, {new_total_ads} total quota (remaining: {new_total_ads})")
            except Exception as e:
                print(f"⚠️ Warning: Could not sync subscription data to user profile: {e}")
                # Don't fail the request if profile sync fails
            
            # Store analysis data in user_analysis collection
            print(f"🔍 DEBUG: About to save adTitle to database: '{adTitle}'")
            analysis_data = {
                "userId": userId,
                "artifact_id": artifact_id,
                "brand_id": brandId,
                "timestamp": timestamp,
                "messageIntent": messageIntent,
                "funnelStage": funnelStage,
                "channels": channels_list,
                "source": source,
                "clientId": clientId,
                "artifacts": artifacts_data,
                "adTitle": adTitle,  # Include ad title for Libraries display
                "mediaUrl": media_url,
                "mediaType": mediaFile.content_type,
                "storagePath": storage_path,
                "mediaCategory": media_type,
                "brandName": brand_name,
                "ai_analysis_results": results,  # Store all AI model responses
                "plan_usage_at_time": {
                    "adsUsed": new_ads_used,
                    "maxAdsPerMonth": max_ads_per_month,
                    "totalAdsRemaining": new_total_ads,
                    "planName": plan_data.get("planName", "Unknown")
                }
            }
            
            # Add logo data to analysis if logo was found in brand data
            if logo_data:
                analysis_data.update(logo_data)
            
            # Save to user_analysis collection with artifact_id as document ID
            db.collection("user_analysis").document(artifact_id).set(analysis_data)
            print(f"✅ AI analysis results saved to user_analysis collection with ID: {artifact_id}")
            print(f"🔍 DEBUG: Saved analysis_data with adTitle: '{analysis_data.get('adTitle', 'NOT_FOUND')}'")
           
        except Exception as e:
            print(f"❌ Analysis failed or could not save results: {str(e)}")
            # Don't update plan usage if analysis failed
            # Return error response without updating plan usage
            raise HTTPException(
                status_code=500, 
                detail=f"Analysis failed: {str(e)}. Plan usage was not updated."
            )
 
        # Get plan type from user's plan selection
        selected_models = list(results.keys())
        try:
            plan_doc = db.collection("PlanSelectionDetails").document(userId).get()
            if plan_doc.exists:
                plan_data = plan_doc.to_dict()
                plan_type = plan_data.get("planName", "lite").lower().replace("incivus_", "")
            else:
                plan_type = "lite"
        except Exception as e:
            print(f"Warning: Could not get plan type: {e}")
            plan_type = "lite"
       
        # Create a more user-friendly response
        response_data = {
            "status": "success",
            "message": f"Analysis completed. {len(successful_models)} out of {len(selected_features)} models succeeded.",
            "artifactId": artifact_id,
            "analysis_summary": {
                "total_models_requested": len(selected_features),
                "successful_models": len(successful_models),
                "failed_models": len(failed_models),
                "success_rate": f"{(len(successful_models) / len(selected_features) * 100):.1f}%" if selected_features else "0%"
            },
            "ai_analysis_results": results,
            "plan_type": plan_type,
            "selected_models": selected_models,
            "plan_usage": {
                "adsUsed": new_ads_used,  # This will be the updated value after successful analysis
                "maxAdsPerMonth": max_ads_per_month,
                "totalAdsRemaining": new_total_ads,  # This will be the updated value after successful analysis
                "planName": plan_data.get("planName", "Unknown"),
                "monthlyLimitReached": new_ads_used >= max_ads_per_month,
                "adsRemaining": max_ads_per_month - new_ads_used,
                "analysis_successful": True
            },
            "media_info": {
                "mediaUrl": media_url,
                "mediaType": mediaFile.content_type,
                "mediaCategory": media_type,
                "filename": mediaFile.filename,
                "fileSize": mediaFile.size
            },
            "brand_info": {
                "brandId": brandId,
                "brandName": brand_name,
                "userId": userId,
                "brandFound": brand_data is not None
            }
        }
        
        # Add logo information to response if logo was found in brand data
        if logo_data:
            response_data["logoInfo"] = {
                "logo_artifact_id": logo_data["logo_artifact_id"],
                "logoUrl": logo_data["logoUrl"],
                "logoStoragePath": logo_data["logoStoragePath"],
                "logoCategory": logo_data["logoCategory"],
                "logoFilename": logo_data["logoFilename"],
                "logoFileSize": logo_data["logoFileSize"],
                "source": "brand_data"
            }
        
        # Add warnings if any models failed
        if failed_models:
            response_data["warnings"] = {
                "failed_models": failed_models,
                "message": f"The following models failed: {', '.join(failed_models)}"
            }
        
        return response_data
 
    except Exception as e:
        print(f"Error saving analysis details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save analysis details: {str(e)}")
 

@app.post("/uploadBrand")
async def upload_brand(
    request: Request,
    userId: str = Form(...),
    brandName: str = Form(...),
    tagline: str = Form(""),
    brandDescription: str = Form(""),
    industryCategory: str = Form(""),
    colorPalette: str = Form(""),  # Pass as comma-separated string
    keyMessages: str = Form(""),   # Pass as comma-separated string
    logoCount: int = Form(...),
):
    try:
        form = await request.form()
        logos = []

        for i in range(logoCount):
            logo_file: UploadFile = form[f"logo_{i}"]
            file_bytes = await logo_file.read()
            base64_str = base64.b64encode(file_bytes).decode("utf-8")

            logos.append({
                "logoFilename": logo_file.filename,
                "logoContentType": logo_file.content_type,
                "logoBase64": base64_str
            })

        brand_doc = {
            "userId": userId,
            "brandName": brandName,
            "tagline": tagline,
            "brandDescription": brandDescription,
            "industryCategory": industryCategory,
            "colorPalette": [c.strip() for c in colorPalette.split(",") if c.strip()],
            "keyMessages": [k.strip() for k in keyMessages.split(",") if k.strip()],
            "logos": logos,
            "timestamp": datetime.utcnow().isoformat()
        }

        db.collection("brandData").add(brand_doc)
        return {"message": "Brand uploaded successfully!"}

    except Exception as e:
        return {"error": f"Error uploading brand: {str(e)}"}
    

@app.post("/upload-images/")
async def upload_images(files: list[UploadFile] = File(...)):
    uploaded_urls = []
 
    for file in files:
        contents = await file.read()
        blob_name = f"images/{uuid.uuid4()}_{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(contents, content_type=file.content_type)
       # blob.make_public()  # Optional: make image accessible via URL
        uploaded_urls.append(blob.public_url)
 
    return {"uploaded_urls": uploaded_urls}

@app.get("/get-brand-data/{brand_id}")
async def get_brand_data(brand_id: str):
    try:
        # Fetch document by ID from Firestore
        doc_ref = db.collection("brandData").document(brand_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Brand data not found")
        
        brand_data = doc.to_dict()
        
        # Generate fresh signed URLs for media files
        if "mediaFiles" in brand_data:
            for media_file in brand_data["mediaFiles"]:
                if "storagePath" in media_file:
                    blob = bucket.blob(media_file["storagePath"])
                    media_file["url"] = blob.generate_signed_url(expiration=3600 * 24 * 7)
        
        return brand_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-user-brands/{user_id}")
async def get_user_brands(user_id: str):
    try:
        # Fetch all brands for a specific user
        docs = db.collection("brandData").where("userId", "==", user_id).stream()
        
        brands = []
        for doc in docs:
            brand_data = doc.to_dict()
            brand_data["brandId"] = doc.id
            
            # Generate fresh signed URLs for media files
            if "mediaFiles" in brand_data:
                for media_file in brand_data["mediaFiles"]:
                    if "storagePath" in media_file:
                        blob = bucket.blob(media_file["storagePath"])
                        media_file["url"] = blob.generate_signed_url(expiration=3600 * 24 * 7)
            
            brands.append(brand_data)
        
        return {"brands": brands, "count": len(brands)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-media-file/{brand_id}/{file_id}")
async def delete_media_file(brand_id: str, file_id: str):
    try:
        # Get brand data
        doc_ref = db.collection("brandData").document(brand_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Brand data not found")
        
        brand_data = doc.to_dict()
        media_files = brand_data.get("mediaFiles", [])
        
        # Find and remove the file
        file_to_delete = None
        updated_media_files = []
        
        for media_file in media_files:
            if media_file.get("fileId") == file_id:
                file_to_delete = media_file
            else:
                updated_media_files.append(media_file)
        
        if not file_to_delete:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        # Delete from blob storage
        if "storagePath" in file_to_delete:
            blob = bucket.blob(file_to_delete["storagePath"])
            if blob.exists():
                blob.delete()
        
        # Update Firestore
        brand_data["mediaFiles"] = updated_media_files
        brand_data["mediaCount"] = len(updated_media_files)
        
        doc_ref.set(brand_data)
        
        return {
            "message": "Media file deleted successfully",
            "deleted_file": file_to_delete,
            "remaining_files": len(updated_media_files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



PLAN_CONFIG = {
    "Incivus_Lite": {"duration_days": 90, "total_ads": 12, "max_ads_per_month": 4, "price": 50},
    "Incivus_Plus": {"duration_days": 180, "total_ads": 30, "max_ads_per_month": 5, "price": 100},
    "Incivus_Pro": {"duration_days": 365, "total_ads": 132, "max_ads_per_month": 11, "price": 400}
}



@app.post("/update_plan")
def update_plan(
    user_id: str = Form(..., description="User ID of the plan owner"),
    plan_name: str = Form(..., description="Plan name: Incivus_Lite / Incivus_Plus / Incivus_Pro"),
    action: str = Form(..., description="Action: topup or upgrade"),
    features: Optional[str] = Form(None, description="Comma-separated list of features for topup only (e.g., 'brand_compliance,content_analysis'). For upgrades, all features are automatically included."),
    total_ads: Optional[int] = Form(None, description="Custom total ads count for upgrades (overrides PLAN_CONFIG default)")
):
    """
    Update user plan with topup or upgrade logic.
    
    Topup Logic:
    - Topup can only be done for the same plan
    - If user buys the same plan before current plan expires, new plan starts from day after current plan expires
    - Example: Lite plan expires on March 31st, topup on March 15th → new plan starts April 1st, expires June 30th
    
    Upgrade Logic:
    - Upgrade can be done to any higher plan
    - New plan starts immediately from the day of upgrade
    - Remaining ads from current plan are carried forward
    - Monthly ad limit becomes the new plan's limit
    - Subscription tenure is exactly as per the new plan's duration
    - All features are automatically included (no features parameter needed)
    """
    try:
        # Validate plan
        plan_info = PLAN_CONFIG.get(plan_name)
        if not plan_info:
            raise HTTPException(status_code=400, detail="Invalid plan name")

        # Define plan hierarchy for upgrades
        PLAN_HIERARCHY = {
            "Incivus_Lite": 1,
            "Incivus_Plus": 2,
            "Incivus_Pro": 3
        }

        # Get Firestore document
        user_ref = db.collection("PlanSelectionDetails").document(user_id)
        doc = user_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User plan not found")

        data = doc.to_dict()
        current_plan_name = data.get("planName", "")
        current_date = datetime.utcnow()
        
        print(f"🔍 Topup request: User {user_id}, Plan: {plan_name}, Action: {action}")
        print(f"🔍 Current plan: {current_plan_name}, Current date: {current_date}")

        # ===== Topup logic =====
        if action == "topup":
            # Check if this is the same plan
            if plan_name != current_plan_name:
                raise HTTPException(status_code=400, detail=f"Topup can only be done for the same plan. Current plan: {current_plan_name}, Requested plan: {plan_name}")
            
            # Parse and validate features for topup
            selected_features = []
            if features:
                try:
                    # Handle different input formats (JSON array, comma-separated, single value)
                    if features.startswith('[') and features.endswith(']'):
                        # JSON array format
                        selected_features = json.loads(features)
                    elif ',' in features:
                        # Comma-separated format
                        selected_features = [feature.strip() for feature in features.split(',') if feature.strip()]
                    else:
                        # Single value format
                        selected_features = [features.strip()] if features.strip() else []
                    
                    print(f"🔍 Parsed features for topup: {selected_features}")
                except json.JSONDecodeError as e:
                    print(f"⚠️ Error parsing features JSON: {e}")
                    selected_features = []
            
            # Get current plan end date
            current_end = datetime.fromisoformat(data["subscriptionEndDate"].replace("Z", ""))
            
            # Check if current plan is still active
            if current_date > current_end:
                # Plan has expired, start new plan from today
                new_start = current_date
                new_end = new_start + timedelta(days=plan_info["duration_days"])
                print(f"✅ Plan expired, starting new plan from today: {new_start} to {new_end}")
            else:
                # Plan is still active, new plan starts from day after current plan expires
                new_start = current_end + timedelta(days=1)
                new_end = new_start + timedelta(days=plan_info["duration_days"])
                print(f"✅ Same plan topup: new plan starts from {new_start} to {new_end}")
            
            # Update plan data
            data["subscriptionStartDate"] = new_start.isoformat() + "Z"
            data["subscriptionEndDate"] = new_end.isoformat() + "Z"
            data["validityDays"] = plan_info["duration_days"]
            # Use custom total_ads if provided, otherwise fall back to PLAN_CONFIG
            topup_ads = total_ads if total_ads is not None else plan_info["total_ads"]
            
            # Get CURRENT remaining ads (this reflects any ads already used)
            current_remaining_ads = data.get("totalAds", 0)
            current_ads_used = data.get("adsUsed", 0)
            
            print(f"🔍 Topup calculation - Current remaining: {current_remaining_ads}, Used: {current_ads_used}, Adding: {topup_ads}")
            
            # Check if current plan has expired
            if current_date > current_end:
                # Plan has expired - Start fresh with new ads only
                data["totalAds"] = topup_ads
                print(f"🔍 Topup (expired plan) - Fresh start: {topup_ads} ads (previous plan expired)")
                # Reset monthly usage for new billing cycle
                data["adsUsed"] = 0
                print(f"🔍 Topup (expired plan) - Reset monthly usage to 0 for new cycle")
            else:
                # Plan is still active - ADD new ads to remaining total
                data["totalAds"] = current_remaining_ads + topup_ads
                print(f"🔍 Topup (active plan) - New total: {data['totalAds']} (remaining {current_remaining_ads} + topup {topup_ads})")
                # PRESERVE monthly usage within same billing cycle
                print(f"🔍 Topup (active plan) - Preserving monthly usage: {current_ads_used} ads used")
            data["max_ads_per_month"] = plan_info["max_ads_per_month"]  # FIX: OVERWRITE for topup (same plan, same monthly limit)
            data["totalPrice"] = data.get("totalPrice", 0) + plan_info.get("price", 100)  # Add price for topup
            # Don't update lastUsageDate during topup - it should only be updated when ads are actually used
            # data["lastUsageDate"] = new_start.isoformat() + "Z"
            data["updatedAt"] = current_date.isoformat() + "Z"
            
            # Update selectedFeatures if provided
            if selected_features:
                data["selectedFeatures"] = selected_features
                print(f"✅ Updated selectedFeatures: {selected_features}")
            else:
                print(f"⚠️ No features provided for topup, keeping existing features: {data.get('selectedFeatures', [])}")
            
            print(f"✅ Same plan topup completed: {plan_name}")
            print(f"📅 New period: {new_start.strftime('%Y-%m-%d')} to {new_end.strftime('%Y-%m-%d')}")
            print(f"📊 Total ads: {data['totalAds']} (added {topup_ads} user-selected ads), Monthly limit: {data['max_ads_per_month']}")

        # ===== Upgrade logic =====
        elif action == "upgrade":
            print(f"🔍 Upgrade request: User {user_id}, Current Plan: {current_plan_name}, New Plan: {plan_name}")
            
            # Check if this is a valid upgrade (higher plan)
            current_plan_level = PLAN_HIERARCHY.get(current_plan_name, 0)
            new_plan_level = PLAN_HIERARCHY.get(plan_name, 0)
            print(f"🔍 Plan levels - Current: {current_plan_level}, New: {new_plan_level}")
            
            if new_plan_level <= current_plan_level:
                raise HTTPException(status_code=400, detail=f"Upgrade can only be done to a higher plan. Current plan: {current_plan_name} (level {current_plan_level}), Requested plan: {plan_name} (level {new_plan_level})")
            
            # Calculate remaining ads from current plan
            remaining_ads = data.get("totalAds", 0)
            current_monthly_limit = data.get("max_ads_per_month", 0)
            print(f"🔍 Current subscription - Remaining ads: {remaining_ads}, Monthly limit: {current_monthly_limit}")
            
            # New plan starts immediately from today
            new_start = current_date
            new_end = new_start + timedelta(days=plan_info["duration_days"])
            print(f"✅ Upgrade plan starts from {new_start.strftime('%Y-%m-%d')} to {new_end.strftime('%Y-%m-%d')}")
            
            # Combine max ads per month from current subscription (actual value) and upgrading plan
            current_max_ads_per_month = data.get("max_ads_per_month", 0)  # Use actual current value, not base plan
            new_plan_max_ads_per_month = plan_info["max_ads_per_month"]
            combined_max_ads_per_month = current_max_ads_per_month + new_plan_max_ads_per_month
            print(f"🔍 DEBUG - Raw data from database: {data}")
            print(f"🔍 DEBUG - Current max_ads_per_month from data: {current_max_ads_per_month}")
            print(f"🔍 DEBUG - New plan max_ads_per_month: {new_plan_max_ads_per_month}")
            print(f"🔍 DEBUG - Combined calculation: {current_max_ads_per_month} + {new_plan_max_ads_per_month} = {combined_max_ads_per_month}")
            print(f"🔍 Monthly limits - Current subscription: {current_max_ads_per_month}, New plan: {new_plan_max_ads_per_month}, Combined: {combined_max_ads_per_month}")

            # Use custom total_ads if provided, otherwise fall back to PLAN_CONFIG
            new_plan_ads = total_ads if total_ads is not None else plan_info["total_ads"]
            print(f"🔍 Upgrade ads calculation - Custom ads: {total_ads}, Config ads: {plan_info['total_ads']}, Using: {new_plan_ads}")
            
            # Update plan data for upgrade
            data["planName"] = plan_name
            data["subscriptionStartDate"] = new_start.isoformat() + "Z"
            data["subscriptionEndDate"] = new_end.isoformat() + "Z"
            data["validityDays"] = plan_info["duration_days"]
            data["totalAds"] = remaining_ads + new_plan_ads  # Carry forward remaining + user-selected ads
            data["max_ads_per_month"] = combined_max_ads_per_month  # Combined monthly limit
            data["totalPrice"] = data.get("totalPrice", 0) + plan_info.get("price", 100)  # Add upgrade price
            # PRESERVE current monthly usage during upgrade - don't reset ads used within the current billing cycle  
            current_ads_used = data.get("adsUsed", 0)
            print(f"🔍 Preserving current monthly usage during upgrade: {current_ads_used} ads used")
            # Don't update lastUsageDate during upgrade - it should only be updated when ads are actually used
            # data["lastUsageDate"] = new_start.isoformat() + "Z"
            data["updatedAt"] = current_date.isoformat() + "Z"
            
            # For upgrades, automatically include all features available in the new plan
            all_features = ["brand_compliance", "content_analysis", "metaphor_analysis", "channel_compliance"]
            data["selectedFeatures"] = all_features
            print(f"✅ Auto-assigned all features for upgrade: {all_features}")
            
            print(f"✅ Plan upgrade completed: {current_plan_name} → {plan_name}")
            print(f"📅 New period: {new_start.strftime('%Y-%m-%d')} to {new_end.strftime('%Y-%m-%d')}")
            print(f"📊 Total ads: {data['totalAds']} (carried forward: {remaining_ads} + user-selected: {new_plan_ads})")
            print(f"📊 Monthly limit: {data['max_ads_per_month']} (combined: {current_max_ads_per_month} + {new_plan_max_ads_per_month})")

        else:
            raise HTTPException(status_code=400, detail="Invalid action type. Use 'topup' or 'upgrade'")

        # Save updated data
        user_ref.update(data)
        
        # SYNC: Also update the user profile subscription data so frontend shows correct data
        try:
            profile_ref = db.collection("userProfileDetails").document(user_id)
            subscription_update = {
                "subscription.planType": data["planName"].replace("Incivus_", "").lower(),
                "subscription.planName": data["planName"],
                "subscription.adQuota": data["totalAds"],
                "subscription.adsUsed": data.get("adsUsed", 0),
                "subscription.max_ads_per_month": data.get("max_ads_per_month", 0),
                "subscription.totalPrice": data.get("totalPrice", 0),  # FIX: Copy total payment amount during topup/upgrade
                "subscription.subscriptionStartDate": data["subscriptionStartDate"],
                "subscription.subscriptionEndDate": data["subscriptionEndDate"],
                "subscription.validityDays": data["validityDays"],
                "subscription.selectedFeatures": data.get("selectedFeatures", []),
                "subscription.updatedAt": data["updatedAt"],
                "updatedAt": data["updatedAt"]
            }
            profile_ref.update(subscription_update)
            print(f"✅ User profile subscription synced after {action}: {data.get('adsUsed', 0)} ads used, {data['totalAds']} total")
        except Exception as e:
            print(f"⚠️ Warning: Could not sync subscription data to user profile after {action}: {e}")
            # Don't fail the request if profile sync fails
        
        # Prepare response data
        response_data = {
            "status": "success", 
            "message": f"Plan {action} completed successfully",
            "updated_data": {
                "planName": data["planName"],
                "subscriptionStartDate": data["subscriptionStartDate"],
                "subscriptionEndDate": data["subscriptionEndDate"],
                "totalAds": data["totalAds"],
                "max_ads_per_month": data["max_ads_per_month"],
                "adsUsed": data["adsUsed"],
                "validityDays": data["validityDays"],
                "selectedFeatures": data.get("selectedFeatures", [])
            },
            "current_plan_end_date": data["subscriptionEndDate"],
            "action_type": action
        }
        
        # Add upgrade-specific information
        if action == "upgrade":
            response_data["previous_plan"] = current_plan_name
            response_data["carried_forward_ads"] = data.get("totalAds", 0) - plan_info["total_ads"]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in update_plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {str(e)}")


@app.post("/sync-subscription-data/{user_id}")
async def sync_subscription_data(user_id: str):
    """
    Manually sync subscription data from PlanSelectionDetails to userProfileDetails
    This is useful for fixing data inconsistency issues
    """
    try:
        # Get data from PlanSelectionDetails (source of truth for backend)
        plan_ref = db.collection("PlanSelectionDetails").document(user_id)
        plan_doc = plan_ref.get()
        
        if not plan_doc.exists:
            raise HTTPException(status_code=404, detail="User plan not found")
        
        plan_data = plan_doc.to_dict()
        
        # Update userProfileDetails with current plan data
        profile_ref = db.collection("userProfileDetails").document(user_id)
        subscription_update = {
            "subscription.planType": plan_data["planName"].replace("Incivus_", "").lower(),
            "subscription.planName": plan_data["planName"],
            "subscription.adQuota": plan_data["totalAds"],
            "subscription.adsUsed": plan_data.get("adsUsed", 0),
            "subscription.max_ads_per_month": plan_data.get("max_ads_per_month", 0),
            "subscription.totalPrice": plan_data.get("totalPrice", 0),  # FIX: Copy total payment amount
            "subscription.subscriptionStartDate": plan_data["subscriptionStartDate"],
            "subscription.subscriptionEndDate": plan_data["subscriptionEndDate"],
            "subscription.validityDays": plan_data["validityDays"],
            "subscription.selectedFeatures": plan_data.get("selectedFeatures", []),
            "subscription.paymentStatus": plan_data.get("paymentStatus", "completed"),
            "subscription.updatedAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        }
        
        profile_ref.update(subscription_update)
        
        return {
            "status": "success",
            "message": "Subscription data synced successfully",
            "synced_data": {
                "planName": plan_data["planName"],
                "adsUsed": plan_data.get("adsUsed", 0),
                "totalAds": plan_data["totalAds"],
                "max_ads_per_month": plan_data.get("max_ads_per_month", 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync subscription data: {str(e)}")

@app.get("/get-plan-status/{user_id}")
async def get_plan_status(user_id: str):
    """
    Get current plan status and topup information
    """
    try:
        # Get user's plan document
        user_ref = db.collection("PlanSelectionDetails").document(user_id)
        doc = user_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="User plan not found")
        
        data = doc.to_dict()
        current_date = datetime.utcnow()
        
        # Parse dates
        start_date = datetime.fromisoformat(data["subscriptionStartDate"].replace("Z", ""))
        end_date = datetime.fromisoformat(data["subscriptionEndDate"].replace("Z", ""))
        
        # Calculate plan status
        is_active = current_date <= end_date
        days_remaining = (end_date - current_date).days if is_active else 0
        days_elapsed = (current_date - start_date).days if current_date >= start_date else 0
        
        # Calculate topup information
        current_plan_name = data.get("planName", "")
        plan_info = PLAN_CONFIG.get(current_plan_name, {})
        
        topup_info = {
            "current_plan": current_plan_name,
            "can_topup": is_active,  # Can only topup if current plan is active
            "next_period_start": (end_date + timedelta(days=1)).strftime("%Y-%m-%d") if is_active else current_date.strftime("%Y-%m-%d"),
            "next_period_end": (end_date + timedelta(days=1 + plan_info.get("duration_days", 0))).strftime("%Y-%m-%d") if is_active else (current_date + timedelta(days=plan_info.get("duration_days", 0))).strftime("%Y-%m-%d"),
            "topup_ads": plan_info.get("total_ads", 0),
            "topup_monthly_limit": plan_info.get("max_ads_per_month", 0)
        }
        
        return {
            "user_id": user_id,
            "plan_status": {
                "plan_name": current_plan_name,
                "is_active": is_active,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days_remaining": days_remaining,
                "days_elapsed": days_elapsed,
                "total_ads": data.get("totalAds", 0),
                "ads_used": data.get("adsUsed", 0),
                "max_ads_per_month": data.get("max_ads_per_month", 0),
                "last_usage_date": data.get("lastUsageDate", "")
            },
            "topup_info": topup_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting plan status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get plan status: {str(e)}")



@app.post("/upload-additional-media/{brand_id}")
async def upload_additional_media(
    brand_id: str,
    mediaType: str = Form(...),  # "logo", "video", or "image"
    metadata: Optional[str] = Form(None),
    files: list[UploadFile] = File(...)
):
    try:
        # Validate brand exists
        doc_ref = db.collection("brandData").document(brand_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Brand data not found")
        
        brand_data = doc.to_dict()
        
        # Allowed file types
        ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
        ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
        
        new_media_files = []
        
        for file in files:
            # Validate file type based on mediaType
            if mediaType in ["logo", "image"]:
                if file.content_type not in ALLOWED_IMAGE_TYPES:
                    raise HTTPException(status_code=400, detail=f"Invalid file type for {mediaType}: {file.content_type}")
            elif mediaType == "video":
                if file.content_type not in ALLOWED_VIDEO_TYPES:
                    raise HTTPException(status_code=400, detail=f"Invalid file type for video: {file.content_type}")
            
            if file.size and file.size > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")
            
            # Generate unique file name
            file_ext = os.path.splitext(file.filename)[1]
            media_id = str(uuid.uuid4())
            storage_filename = f"brands/{brand_id}/{mediaType}s/{media_id}{file_ext}"
            
            # Upload to GCS
            blob = bucket.blob(storage_filename)
            blob.upload_from_file(file.file, content_type=file.content_type)
            #media_url = blob.generate_signed_url(expiration=3600 * 24 * 7)
            media_url = blob.generate_signed_url(
                version="v4",                # use v4 signed URLs
                expiration=timedelta(days=7), # 7 days from now
                method="GET"                  # HTTP method allowed
            )
            
            new_media_files.append({
                "fileId": media_id,
                "filename": file.filename,
                "contentType": file.content_type,
                "fileSize": file.size,
                "url": media_url,
                "storagePath": storage_filename,
                "mediaType": mediaType,
                "metadata": metadata or "",
                "uploadTimestamp": datetime.utcnow().isoformat()
            })
        
        # Update brand data
        existing_media = brand_data.get("mediaFiles", [])
        updated_media = existing_media + new_media_files
        
        brand_data["mediaFiles"] = updated_media
        brand_data["mediaCount"] = len(updated_media)
        
        doc_ref.set(brand_data)
        
        return {
            "message": f"Additional {mediaType} files uploaded successfully",
            "brand_id": brand_id,
            "uploaded_files": new_media_files,
            "total_media_count": len(updated_media)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-analysis-details/{user_id}")
async def get_analysis_details(user_id: str):
    try:
        # Step 1: Get selected features from PlanSelectionDetails
        try:
            plans_selection = db.collection("PlanSelectionDetails").document(user_id)
            get_plans = plans_selection.get()
            
            if get_plans.exists:
                plan_data = get_plans.to_dict()
                selected_features = plan_data.get("selectedFeatures", [])
            else:
                selected_features = []
        except Exception as e:
            print(f"Error fetching selected features: {e}")
            selected_features = []

        print(selected_features)
        # Step 2: Get analysis documents for the user from user_analysis collection
        docs = db.collection("user_analysis").where("userId", "==", user_id).stream()
        
        analysis_details = []

        for doc in docs:
            data = doc.to_dict()
            
            # Filter ai_analysis_results by selected_features
            if "ai_analysis_results" in data and selected_features:
                # Check if comprehensive-analysis exists and has data.results
                if "comprehensive-analysis" in data["ai_analysis_results"]:
                    comp_analysis = data["ai_analysis_results"]["comprehensive-analysis"]
                    if "data" in comp_analysis and "results" in comp_analysis["data"]:
                        original_features = comp_analysis["data"]["results"]
                        
                        # Map plan features to nested results features
                        feature_mapping = {
                            "brand_compliance": "brand_compliance",
                            "channel_compliance": "channel_compliance", 
                            "content_analysis": "content_analysis",
                            "metaphor_analysis": "metaphor_analysis",
                            "messaging_intent": "content_analysis",  # messaging intent maps to content analysis
                            "funnel_compatibility": "content_analysis",  # funnel compatibility maps to content analysis
                            "resonance_index": "metaphor_analysis"  # resonance index maps to metaphor analysis
                        }
                        
                        # Create filtered results structure
                        filtered_results = {}
                        filtered_features = []
                        
                        # Filter the nested features based on user's plan
                        for plan_feature in selected_features:
                            if plan_feature in feature_mapping:
                                nested_feature = feature_mapping[plan_feature]
                                if nested_feature in original_features:
                                    filtered_results[nested_feature] = original_features[nested_feature]
                                    filtered_features.append(nested_feature)
                        
                        # Create filtered comprehensive analysis
                        filtered_comp_analysis = comp_analysis.copy()
                        filtered_comp_analysis["data"] = comp_analysis["data"].copy()
                        filtered_comp_analysis["data"]["results"] = filtered_results
                        
                        # Update the analysis data
                        data["ai_analysis_results"]["comprehensive-analysis"] = filtered_comp_analysis
                        data["filtered_features"] = filtered_features
                        data["total_filtered_features"] = len(filtered_features)
                        data["filtered_models"] = ["comprehensive-analysis"]
                        data["total_filtered_models"] = 1
                        
                        print(f"✅ Filtered features for analysis {doc.id}: {filtered_features}")
                        print(f"🔍 User selected features: {selected_features}")
                        print(f"🔍 Available features in results: {list(original_features.keys())}")
                    else:
                        data["filtered_features"] = []
                        data["total_filtered_features"] = 0
                        data["filtered_models"] = []
                        data["total_filtered_models"] = 0
                else:
                    data["filtered_features"] = []
                    data["total_filtered_features"] = 0
                    data["filtered_models"] = []
                    data["total_filtered_models"] = 0
            
            data["document_id"] = doc.id
            data["user_selected_features"] = selected_features
            analysis_details.append(data)

        if not analysis_details:
            raise HTTPException(status_code=404, detail=f"No analysis details found for user: {user_id}")
        
        return {
            "user_id": user_id,
            "total_analyses": len(analysis_details),
            "user_selected_features": selected_features,
            "analysis_details": analysis_details
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

 
@app.get("/get-user-analysis-history/{user_id}")
async def get_user_analysis_history(user_id: str):
    """Get all analysis results for a specific user"""
    try:
        # Query all documents for this user from user_analysis collection
        docs = db.collection("user_analysis").where("userId", "==", user_id).stream()
       
        analysis_history = []
        for doc in docs:
            data = doc.to_dict()
            analysis_history.append({
                "artifact_id": doc.id,
                "timestamp": data.get("timestamp"),
                "messageIntent": data.get("messageIntent"),  # metaphor analysis
                "funnelStage": data.get("funnelStage"),  # funnel compatibility
                "channels": data.get("channels"),  # channel compliance
                "adTitle": data.get("adTitle"),  # Ad title for Libraries display
                "total_models_analyzed": data.get("total_models_analyzed"),
                "successful_models": data.get("successful_models"),
                "ai_analysis_results": data.get("ai_analysis_results"),
                "plan_usage_at_time": data.get("plan_usage_at_time", {})
            })
       
        return {
            "user_id": user_id,
            "total_analyses": len(analysis_history),
            "analysis_history": analysis_history
        }
 
    except Exception as e:
        print(f"Error fetching user analysis history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-analysis-by-id/{analysis_id}")
async def get_analysis_by_id(analysis_id: str):
    """Get a specific analysis result by analysis ID with feature filtering based on user's plan"""
    try:
        doc_ref = db.collection("user_analysis").document(analysis_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Analysis with ID '{analysis_id}' not found")
        
        analysis_data = doc.to_dict()
        analysis_data["document_id"] = doc.id
        print(f"✅ Analysis data: {analysis_data}")
        
        # Get user ID from the analysis data
        user_id = analysis_data.get("userId")
        if not user_id:
            raise HTTPException(status_code=400, detail="Analysis data does not contain user ID")
        
        # Get selected features from user's plan
        selected_features = []
        try:
            plan_doc = db.collection("PlanSelectionDetails").document(user_id).get()
            if plan_doc.exists:
                plan_data = plan_doc.to_dict()
                selected_features = plan_data.get("selectedFeatures", [])
                print(f"✅ Found selected features for user {user_id}: {selected_features}")
            else:
                print(f"⚠️ No plan found for user {user_id}, showing all features")
                selected_features = []
        except Exception as e:
            print(f"Warning: Could not get selected features for user {user_id}: {e}")
            selected_features = []
        
        # Filter AI analysis results based on selected features
        if "ai_analysis_results" in analysis_data and selected_features:
            original_results = analysis_data["ai_analysis_results"]
            
            # Check if comprehensive-analysis exists and has data.results
            if "comprehensive-analysis" in original_results:
                comp_analysis = original_results["comprehensive-analysis"]
                if "data" in comp_analysis and "results" in comp_analysis["data"]:
                    original_features = comp_analysis["data"]["results"]
                    
                    # Create filtered results structure
                    filtered_results = {}
                    filtered_features = []
                    
                    # Map plan features to nested results features based on actual response structure
                    feature_mapping = {
                        "brand_compliance": "brand_compliance",
                        "channel_compliance": "channel_compliance", 
                        "messaging_intent": "content_analysis",  # messaging intent maps to content analysis
                        "funnel_compatibility": "content_analysis",  # funnel compatibility maps to content analysis
                        "resonance_index": "metaphor_analysis"  # resonance index maps to metaphor analysis
                    }
                    
                    # Filter the nested features based on user's plan
                    for plan_feature in selected_features:
                        if plan_feature in feature_mapping:
                            nested_feature = feature_mapping[plan_feature]
                            if nested_feature in original_features:
                                filtered_results[nested_feature] = original_features[nested_feature]
                                filtered_features.append(nested_feature)
                    
                    # Create filtered comprehensive analysis
                    filtered_comp_analysis = comp_analysis.copy()
                    filtered_comp_analysis["data"] = comp_analysis["data"].copy()
                    filtered_comp_analysis["data"]["results"] = filtered_results
                    
                    # Update the analysis data
                    analysis_data["ai_analysis_results"]["comprehensive-analysis"] = filtered_comp_analysis
                    analysis_data["filtered_features"] = filtered_features
                    analysis_data["total_filtered_features"] = len(filtered_features)
                    analysis_data["user_selected_features"] = selected_features
                    analysis_data["all_available_features"] = list(original_features.keys())
                    
                    print(f"✅ Filtered nested features: {filtered_features} out of {list(original_features.keys())}")
                    print(f"🔍 User selected features: {selected_features}")
                    print(f"🔍 Available features in results: {list(original_features.keys())}")
                    print(f"🔍 Feature mapping used: {feature_mapping}")
                else:
                    print(f"⚠️ No 'data.results' found in comprehensive-analysis")
                    analysis_data["filtered_features"] = []
                    analysis_data["total_filtered_features"] = 0
                    analysis_data["user_selected_features"] = selected_features
                    analysis_data["all_available_features"] = []
            else:
                print(f"⚠️ No 'comprehensive-analysis' found in ai_analysis_results")
                analysis_data["filtered_features"] = []
                analysis_data["total_filtered_features"] = 0
                analysis_data["user_selected_features"] = selected_features
                analysis_data["all_available_features"] = []
        else:
            # If no features selected or no filtering needed, show all results
            if "ai_analysis_results" in analysis_data and "comprehensive-analysis" in analysis_data["ai_analysis_results"]:
                comp_analysis = analysis_data["ai_analysis_results"]["comprehensive-analysis"]
                if "data" in comp_analysis and "results" in comp_analysis["data"]:
                    all_features = list(comp_analysis["data"]["results"].keys())
                    analysis_data["filtered_features"] = all_features
                    analysis_data["total_filtered_features"] = len(all_features)
                    analysis_data["user_selected_features"] = selected_features
                    analysis_data["all_available_features"] = all_features
                else:
                    analysis_data["filtered_features"] = []
                    analysis_data["total_filtered_features"] = 0
                    analysis_data["user_selected_features"] = selected_features
                    analysis_data["all_available_features"] = []
            else:
                analysis_data["filtered_features"] = []
                analysis_data["total_filtered_features"] = 0
                analysis_data["user_selected_features"] = selected_features
                analysis_data["all_available_features"] = []
        
        return {
            "message": "Analysis retrieved successfully",
            "analysis": analysis_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis: {str(e)}")


@app.post("/reset-monthly-usage/{user_id}")
async def reset_monthly_usage(user_id: str):
    """Manually reset monthly usage for a user (for testing purposes)"""
    try:
        plan_ref = db.collection("PlanSelectionDetails").document(user_id)
        plan_doc = plan_ref.get()
        
        if not plan_doc.exists:
            raise HTTPException(status_code=404, detail="User plan not found")
        
        plan_data = plan_doc.to_dict()
        current_date = datetime.utcnow()
        
        updates = {
            "adsUsed": 0,
            "lastUsageDate": current_date.isoformat() + "Z",
            "updatedAt": current_date.isoformat() + "Z"
        }
        
        plan_ref.update(updates)
        
        return {
            "message": "Monthly usage reset successfully",
            "user_id": user_id,
            "reset_date": current_date.isoformat(),
            "new_ads_used": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error resetting monthly usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset monthly usage: {str(e)}")


@app.post("/reset-all-monthly-usage")
async def reset_all_monthly_usage():
    """Reset monthly usage for all users (scheduled task)"""
    try:
        current_date = datetime.utcnow()
        reset_count = 0
        
        # Get all plan documents
        docs = db.collection("PlanSelectionDetails").stream()
        
        for doc in docs:
            plan_data = doc.to_dict()
            last_usage_date = plan_data.get("lastUsageDate")
            
            # Check if reset is needed
            if last_usage_date:
                try:
                    last_usage = datetime.fromisoformat(last_usage_date.replace("Z", ""))
                    # Reset if it's a new month
                    if (current_date.year != last_usage.year or current_date.month != last_usage.month):
                        updates = {
                            "adsUsed": 0,
                            "lastUsageDate": current_date.isoformat() + "Z",
                            "updatedAt": current_date.isoformat() + "Z"
                        }
                        doc.reference.update(updates)
                        reset_count += 1
                        print(f"🔄 Reset monthly usage for user: {doc.id}")
                except Exception as e:
                    print(f"Warning: Could not parse last usage date for user {doc.id}: {e}")
                    continue
        
        return {
            "message": "Monthly usage reset completed",
            "reset_date": current_date.isoformat(),
            "users_reset": reset_count
        }
        
    except Exception as e:
        print(f"Error in monthly reset task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset monthly usage: {str(e)}")

@app.get("/get-plan-selections/{user_id}")
async def get_plan_selections(user_id: str):
    try:
        docs = db.collection("PlanSelectionDetails").where("userId", "==", user_id).stream()
        plans: list[dict] = []
        for doc in docs:
            d = doc.to_dict() or {}
            plans.append({
                "planId": d.get("planId"),
                "planName": d.get("planName"),
                "selected_features": d.get("selectedFeatures", []),
                "subscriptionStartDate": d.get("subscriptionStartDate"),
                "subscriptionEndDate": d.get("subscriptionEndDate"),
                "paymentStatus": d.get("paymentStatus"),
                "totalAds": d.get("totalAds"),
                "totalPrice": d.get("totalPrice"),
                "validityDays": d.get("validityDays"),
            })
        if not plans:
            raise HTTPException(status_code=404, detail=f"No plans found for user: {user_id}")
        return {"userId": user_id, "count": len(plans), "plans": plans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching plans: {str(e)}")


@app.get("/get-user-files/{user_id}")
async def get_user_files(user_id: str, fileType: Optional[str] = None, limit: int = 50):
    """Return user files for a user. Frontend should call this instead of Firestore directly."""
    try:
        def query_collection(collection_name: str):
            q = db.collection(collection_name).where("userId", "==", user_id)
            if fileType:
                q = q.where("fileType", "==", fileType)
            docs = list(q.stream())
            files: list[dict] = []
            for d in docs:
                data = d.to_dict() or {}
                data["id"] = d.id
                files.append(data)
            # Sort by createdAt if present
            def ts(entry: dict):
                val = entry.get("createdAt")
                if isinstance(val, dict) and "seconds" in val:
                    return val.get("seconds", 0)
                return 0
            files.sort(key=ts, reverse=True)
            return files

        files = query_collection("userFiles")
        if not files:
            files = query_collection("UserFiles")

        if limit and limit > 0:
            files = files[:limit]

        return {"userId": user_id, "count": len(files), "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user files: {str(e)}")


@app.get("/get-user-file/{file_id}")
async def get_user_file(file_id: str):
    """Return a single user file document by ID."""
    try:
        def get_from(collection_name: str):
            d = db.collection(collection_name).document(file_id).get()
            if d.exists:
                data = d.to_dict() or {}
                data["id"] = d.id
                return data
            return None

        data = get_from("userFiles") or get_from("UserFiles")
        if data is None:
            raise HTTPException(status_code=404, detail="File not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user file: {str(e)}")


# ===============================
# Analysis persistence endpoints
# ===============================

@app.post("/save-analysis-record")
async def save_analysis_record(request: Request):
    """Persist analysis inputs and results metadata into userFiles collection."""
    try:
        body = await request.json()
        user_id = body.get("userId")
        if not user_id:
            raise HTTPException(status_code=400, detail="userId required")

        now = datetime.utcnow()
        doc = {
            "userId": user_id,
            "fileCategory": "analysis-report",
            "fileType": "application/json",
            "fileName": body.get("fileName") or "Ad Analysis",
            "analysisInputs": body.get("analysisInputs", {}),
            "analysisResults": body.get("analysisResults", {}),
            "analysisId": body.get("analysisId"),
            "createdAt": now,
            "updatedAt": now,
            "tags": ["analysis", "report"],
        }

        ref = db.collection("userFiles").document()
        ref.set(doc)
        doc_id = ref.id
        doc["id"] = doc_id
        return {"message": "Analysis record saved", "id": doc_id, "document": doc}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving analysis record: {str(e)}")










@app.post("/upload-analysis-pdf")
async def upload_analysis_pdf(
    userId: str = Form(...),
    file: UploadFile = File(...),
    analysisId: Optional[str] = Form(None),
    fileName: Optional[str] = Form(None),
):
    """Upload a generated analysis PDF to GCS and create/update a userFiles document."""
    try:
        if not userId:
            raise HTTPException(status_code=400, detail="userId required")

        safe_name = (fileName or file.filename or "analysis.pdf").replace("/", "_")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        storage_path = f"analysis-reports/{userId}/{ts}_{safe_name}"

        contents = await file.read()
        blob = bucket.blob(storage_path)
        blob.upload_from_string(contents, content_type="application/pdf")
        #url = blob.generate_signed_url(expiration=3600 * 24 * 7)
        url = blob.generate_signed_url(
                version="v4",                # use v4 signed URLs
                expiration=timedelta(days=7), # 7 days from now
                method="GET"                  # HTTP method allowed
            )

        payload = {
            "userId": userId,
            "fileCategory": "analysis-report",
            "fileType": "application/pdf",
            "fileName": safe_name,
            "storagePath": storage_path,
            "url": url,
            "analysisId": analysisId,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            "tags": ["analysis", "pdf"],
        }

        doc_id = None
        if analysisId:
            matches = list(db.collection("userFiles").where("userId", "==", userId).where("analysisId", "==", analysisId).limit(1).stream())
            if matches:
                doc_ref = db.collection("userFiles").document(matches[0].id)
                doc_ref.set(payload, merge=True)
                doc_id = matches[0].id
        if not doc_id:
            doc_ref = db.collection("userFiles").document()
            doc_ref.set(payload)
            doc_id = doc_ref.id

        return {"message": "PDF uploaded", "id": doc_id, "url": url, "storagePath": storage_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading analysis PDF: {str(e)}")


@app.post("/create-std-plan-details")
async def create_std_plan_details():
    """
    Create standard plan details in the std_plan_details collection.
    This endpoint initializes the collection with the three standard plans.
    """
    try:
        # Standard plan details based on the provided table
        std_plans = [
            {
                "planName": "Incivus_Lite",
                "usp": "4/5",
                "duration": "3 Months",
                "durationDays": 90,
                "pricePerAd": 5.0,
                "minOrderQty": 10,
                "minCommitment": 50,
                "maxAdsPerMonth": 4,
                "totalAds": 12
            },
            {
                "planName": "Incivus_Plus",
                "usp": "5/5",
                "duration": "6 Months", 
                "durationDays": 180,
                "pricePerAd": 4.0,
                "minOrderQty": 25,
                "minCommitment": 100,
                "maxAdsPerMonth": 5,
                "totalAds": 30
            },
            {
                "planName": "Incivus_Pro", 
                "usp": "5/5",
                "duration": "12 months",
                "durationDays": 365,
                "pricePerAd": 3.2,
                "minOrderQty": 125,
                "minCommitment": 400,
                "maxAdsPerMonth": 11,
                "totalAds": 132
            }
        ]
        
        # Store each plan in the std_plan_details collection
        for plan in std_plans:
            plan_id = plan["planName"]
            db.collection("std_plan_details").document(plan_id).set(plan)
            print(f"✅ Created plan: {plan['planName']}")
        
        return {
            "message": "Standard plan details created successfully",
            "plans_created": len(std_plans),
            "plans": std_plans
        }
        
    except Exception as e:
        print(f"Error creating standard plan details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create standard plan details: {str(e)}")

@app.delete("/delete-user-file/{user_id}/{file_id}")
async def delete_user_file(user_id: str, file_id: str):
    """
    Delete a user file from user_analysis collection
    """
    try:
        # Query user_analysis collection for the file
        analysis_ref = db.collection("user_analysis")
        query = analysis_ref.where("userId", "==", user_id).where("artifact_id", "==", file_id)
        docs = query.get()
        
        if not docs:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete all matching documents
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        return {
            "message": f"Successfully deleted {deleted_count} file(s)",
            "file_id": file_id,
            "user_id": user_id
        }
        
    except Exception as e:
        print(f"❌ Error deleting user file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-file/{file_id}")
async def delete_file_by_id(file_id: str):
    """
    Delete a file by ID from user_analysis collection (fallback endpoint)
    """
    try:
        # Query user_analysis collection for the file
        analysis_ref = db.collection("user_analysis")
        query = analysis_ref.where("artifact_id", "==", file_id)
        docs = query.get()
        
        if not docs:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete all matching documents
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        return {
            "message": f"Successfully deleted {deleted_count} file(s)",
            "file_id": file_id
        }
        
    except Exception as e:
        print(f"❌ Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fix-plan-quota/{user_id}")
async def fix_plan_quota(user_id: str):
    """
    Fix incorrect adQuota values in user profiles based on their actual plan type
    """
    try:
        # Get user's current plan from PlanSelectionDetails
        plan_ref = db.collection("PlanSelectionDetails").document(user_id)
        plan_doc = plan_ref.get()
        
        if not plan_doc.exists:
            raise HTTPException(status_code=404, detail="User plan not found")
        
        plan_data = plan_doc.to_dict()
        plan_name = plan_data.get("planName", "")
        
        # Get correct quota from PLAN_CONFIG
        if plan_name not in PLAN_CONFIG:
            raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_name}")
        
        correct_total_ads = PLAN_CONFIG[plan_name]["total_ads"]
        correct_max_ads_per_month = PLAN_CONFIG[plan_name]["max_ads_per_month"]
        current_ads_used = plan_data.get("adsUsed", 0)
        
        # Update PlanSelectionDetails with correct values
        plan_ref.update({
            "totalAds": correct_total_ads,
            "max_ads_per_month": correct_max_ads_per_month,
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        })
        
        # Update userProfileDetails with correct values
        profile_ref = db.collection("userProfileDetails").document(user_id)
        profile_ref.update({
            "subscription.adQuota": correct_total_ads,
            "subscription.max_ads_per_month": correct_max_ads_per_month,
            "subscription.updatedAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        })
        
        return {
            "success": True,
            "message": f"Fixed quota for {plan_name}",
            "details": {
                "planName": plan_name,
                "correctTotalAds": correct_total_ads,
                "correctMaxAdsPerMonth": correct_max_ads_per_month,
                "currentAdsUsed": current_ads_used,
                "remainingAds": correct_total_ads - current_ads_used
            }
        }
        
    except Exception as e:
        print(f"❌ Error fixing plan quota: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete-user-subscription/{user_id}")
async def delete_user_subscription(user_id: str):
    """
    Delete all subscription data for a user to allow fresh testing
    """
    try:
        # Delete from PlanSelectionDetails
        plan_ref = db.collection("PlanSelectionDetails").document(user_id)
        if plan_ref.get().exists:
            plan_ref.delete()
            print(f"✅ Deleted PlanSelectionDetails for user {user_id}")
        
        # Delete subscription data from userProfileDetails
        profile_ref = db.collection("userProfileDetails").document(user_id)
        profile_doc = profile_ref.get()
        
        if profile_doc.exists:
            # Delete nested subscription fields first
            subscription_fields = [
                "subscription.adQuota",
                "subscription.adsUsed", 
                "subscription.max_ads_per_month",
                "subscription.totalPrice",
                "subscription.basePrice",
                "subscription.paymentStatus",
                "subscription.planType",
                "subscription.planName",
                "subscription.isActive",
                "subscription.status",
                "subscription.validityDays",
                "subscription.subscriptionStartDate",
                "subscription.subscriptionEndDate",
                "subscription.features",
                "subscription.selectedFeatures",
                "subscription.subscribed",
                "subscription.lastUpdated",
                "subscription.updatedAt"
            ]
            
            # Delete nested fields
            update_data = {}
            for field in subscription_fields:
                update_data[field] = firestore.DELETE_FIELD
            
            if update_data:
                profile_ref.update(update_data)
                print(f"✅ Deleted subscription fields from userProfileDetails for user {user_id}")
            
            # Then delete the main subscription object
            profile_ref.update({"subscription": firestore.DELETE_FIELD})
            print(f"✅ Deleted main subscription object for user {user_id}")
        
        return {
            "success": True,
            "message": f"All subscription data deleted for user {user_id}",
            "user_id": user_id
        }
        
    except Exception as e:
        print(f"❌ Error deleting subscription data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-fresh-subscription")
async def create_fresh_subscription(
    user_id: str = Form(...),
    plan_name: str = Form(...),
    total_ads: int = Form(...),
    max_ads_per_month: int = Form(...),
    price: int = Form(...)
):
    """
    Create a fresh subscription with correct values
    """
    try:
        from datetime import datetime, timedelta
        
        # Get plan config
        plan_info = PLAN_CONFIG.get(plan_name)
        if not plan_info:
            raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_name}")
        
        # Create timestamps
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=plan_info["duration_days"])
        
        # Create PlanSelectionDetails entry
        plan_data = {
            "userId": user_id,
            "planName": plan_name,
            "planType": plan_name.split('_')[1].lower(),  # Extract 'lite', 'plus', 'pro'
            "totalAds": total_ads,
            "max_ads_per_month": max_ads_per_month,
            "adsUsed": 0,
            "basePrice": price,
            "totalPrice": price,
            "paymentStatus": "pending",
            "isActive": True,
            "status": "active",
            "validityDays": plan_info["duration_days"],
            "subscriptionStartDate": start_date.isoformat() + "Z",
            "subscriptionEndDate": end_date.isoformat() + "Z",
            "features": ["brand_compliance", "messaging_intent", "funnel_compatibility", "channel_compliance"],
            "selectedFeatures": ["brand_compliance", "messaging_intent", "funnel_compatibility", "channel_compliance"],
            "subscribed": True,
            "subscriptionType": "new",
            "createdAt": start_date.isoformat() + "Z",
            "updatedAt": start_date.isoformat() + "Z"
        }
        
        # Save to PlanSelectionDetails
        db.collection("PlanSelectionDetails").document(user_id).set(plan_data)
        
        # Create subscription data for userProfileDetails
        subscription_data = {
            "subscription": {
                "adQuota": total_ads,
                "adsUsed": 0,
                "max_ads_per_month": max_ads_per_month,
                "totalPrice": price,
                "basePrice": price,
                "paymentStatus": "pending",
                "planType": plan_name.split('_')[1].lower(),
                "planName": plan_name,
                "isActive": True,
                "status": "active",
                "validityDays": plan_info["duration_days"],
                "subscriptionStartDate": start_date.isoformat() + "Z",
                "subscriptionEndDate": end_date.isoformat() + "Z",
                "features": ["brand_compliance", "messaging_intent", "funnel_compatibility", "channel_compliance"],
                "selectedFeatures": ["brand_compliance", "messaging_intent", "funnel_compatibility", "channel_compliance"],
                "subscribed": True,
                "lastUpdated": start_date.isoformat() + "Z",
                "updatedAt": start_date.isoformat() + "Z"
            },
            "updatedAt": start_date.isoformat() + "Z"
        }
        
        # Update userProfileDetails
        db.collection("userProfileDetails").document(user_id).update(subscription_data)
        
        print(f"✅ Created fresh {plan_name} subscription for user {user_id}")
        
        return {
            "success": True,
            "message": f"Fresh {plan_name} subscription created",
            "plan_data": plan_data,
            "subscription_data": subscription_data["subscription"]
        }
        
    except Exception as e:
        print(f"❌ Error creating fresh subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

