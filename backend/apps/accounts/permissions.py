from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow owners to edit"""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj == request.user


class VerifiedUserPermission(permissions.BasePermission):
    """Allow access only to verified users"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.verification_level >= 1