from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Customer
from .serializers import (
    CustomerSignupSerializer,
    CustomerLoginSerializer,
    CustomerProfileSerializer
)


class SignupView(APIView):
    """Customer signup"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = CustomerSignupSerializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(customer)
            
            return Response({
                'message': 'Account created successfully',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'customer': CustomerProfileSerializer(customer).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """Customer login"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = CustomerLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            customer = serializer.validated_data['customer']
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(customer)
            
            return Response({
                'message': 'Login successful',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'customer': CustomerProfileSerializer(customer).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """Customer logout - blacklist refresh token"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Logged out successfully'})
    except Exception:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )


class ProfileView(RetrieveUpdateAPIView):
    """Get and update customer profile"""
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user