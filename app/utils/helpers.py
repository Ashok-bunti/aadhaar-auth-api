import re

def calculate_address_perfection(data):
    """Calculates a score based on presence of key address components."""
    score = 0
    components = []
    
    if data.get("pincode") and re.match(r'^\d{6}$', str(data["pincode"])):
        score += 40
        components.append("Pincode")
    if data.get("state"):
        score += 20
        components.append("State")
    if data.get("district") or data.get("city") or data.get("address"):
        score += 20
        components.append("City/Dist")
    if data.get("house") or data.get("street") or (data.get("address") and len(str(data.get("address"))) > 15):
        score += 20
        components.append("Local Address")
        
    status = "Perfect" if score >= 85 else "Incomplete" if score < 50 else "Good"
    return score, status, components
