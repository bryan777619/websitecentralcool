from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from .models import Rating
from .forms import RatingForm

@login_required
def create_rating(request):
    # Check if user already has a rating
    if Rating.objects.filter(user=request.user).exists():
        messages.warning(request, 'Anda sudah membuat penilaian sebelumnya.')
        return redirect('ratings:view_ratings')

    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.user = request.user
            rating.save()
            messages.success(request, 'Terima kasih! Penilaian Anda telah berhasil disimpan.')
            return redirect('ratings:view_ratings')
    else:
        form = RatingForm()

    return render(request, 'ratings/create_rating.html', {
        'form': form,
        'title': 'Buat Penilaian'
    })

def view_ratings(request):
    ratings = Rating.objects.select_related('user').all()
    user_has_rating = request.user.is_authenticated and Rating.objects.filter(user=request.user).exists()

    return render(request, 'ratings/view_ratings.html', {
        'ratings': ratings,
        'title': 'Semua Penilaian',
        'user_has_rating': user_has_rating
    })

@login_required
def check_user_rating(request):
    has_rating = Rating.objects.filter(user=request.user).exists()
    return JsonResponse({'has_rating': has_rating})

@login_required
def edit_rating(request, rating_id):
    rating = get_object_or_404(Rating, id=rating_id)
    
    # Check if the user owns this rating
    if rating.user != request.user:
        return HttpResponseForbidden("You don't have permission to edit this rating.")
        
    if request.method == 'POST':
        form = RatingForm(request.POST, instance=rating)
        if form.is_valid():
            form.save()
            messages.success(request, 'Penilaian Anda berhasil diperbarui.')
            return redirect('ratings:view_ratings')
    else:
        form = RatingForm(instance=rating)
    
    return render(request, 'ratings/edit_rating.html', {
        'form': form,
        'rating': rating,
        'title': 'Edit Penilaian'
    })