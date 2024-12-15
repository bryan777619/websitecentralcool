from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from .models import Reservasi, Recommendation, RecommendationUsage
from django.core.exceptions import ValidationError
from .forms import ReservasiForm, RecommendationForm
from django.http import JsonResponse, Http404
from .ml_service import recommender
import os
from django.conf import settings
from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from datetime import datetime
from .models import PredictionHistory

@login_required 
def home(request): 
    user_reservations = Reservasi.objects.filter(
        user=request.user,
        is_cancelled=False
    ).order_by('-tanggal', '-waktu')
    
    context = {
        'user': request.user,
        'user_reservations': user_reservations,
    }
    return render(request, 'reservasi/home.html', context)

@login_required
def buat_reservasi(request):
    if request.method == 'POST':
        form = ReservasiForm(request.POST)
        if form.is_valid():
            reservasi = form.save(commit=False)
            reservasi.user = request.user
            reservasi.status = 'Dalam Perbaikan'
            reservasi.created_at = timezone.now()
            reservasi.save()
            messages.success(request, 'Reservasi berhasil dibuat!')
            return redirect('home')
    else:
        form = ReservasiForm()

    return render(request, 'reservasi/buat_reservasi.html', {'form': form})

@login_required
def riwayat_reservasi(request):
    user_reservations = Reservasi.objects.filter(
        user=request.user
    ).order_by('-tanggal', '-waktu')
    
    # Hitung total pembayaran untuk reservasi yang selesai
    total_payments = sum(
        reservasi.nominal_pembayaran or 0 
        for reservasi in user_reservations 
        if reservasi.status == 'Selesai'
    )
    
    return render(request, 'reservasi/riwayat_reservasi.html', {
        'reservations': user_reservations,
        'total_payments': total_payments
    })

@login_required
def get_recommendation(request):
    try:
        # Check active reservation
        active_reservation = Reservasi.objects.filter(
            user=request.user,
            status='Dalam Perbaikan',
            is_cancelled=False
        ).first()
        
        if not active_reservation:
            messages.error(request, 'Anda harus memiliki reservasi aktif untuk mengakses fitur rekomendasi.')
            return redirect('home')
        
        usage, created = RecommendationUsage.objects.get_or_create(
            user=request.user,
            current_reservation=active_reservation,
            defaults={'used_count': 0}
        )

        USAGE_LIMIT = 5
        remaining_uses = max(0, USAGE_LIMIT - usage.used_count)

        # Get prediction history for initial context
        prediction_history = PredictionHistory.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]

        context = {
            'form': RecommendationForm(),
            'remaining_uses': remaining_uses,
            'recommendation_result': None,
            'prediction_history': prediction_history
        }
        
        if request.method == 'POST':
            form = RecommendationForm(request.POST)
            if form.is_valid():
                if usage.used_count >= USAGE_LIMIT:
                    messages.error(request, 'Anda telah mencapai batas maksimal penggunaan fitur rekomendasi perawatan.')
                    return redirect('get_recommendation')
                    
                try:
                    # Get form data
                    problems = form.cleaned_data['problems']
                    car_type = form.cleaned_data['car_type']
                    car_brand = form.cleaned_data['car_brand']
                    
                    # Process each problem separately
                    predictions = []
                    confidences = []
                    descriptions = []
                    
                    for problem in problems:
                        # Get prediction for each problem
                        prediction, confidence, _ = recommender.predict(
                            symptom=problem.description,
                            car_type=car_type.name.lower(),
                            car_brand=car_brand.name.lower()
                        )
                        
                        predictions.append(prediction)
                        confidences.append(confidence)
                        descriptions.append(recommender.get_service_description(prediction))
                    
                    # Save recommendation
                    recommendation = Recommendation.objects.create(
                        user=request.user,
                        car_type=car_type,
                        car_brand=car_brand,
                        recommended_services=predictions,
                        service_descriptions=descriptions,
                        ml_model_used=recommender.best_model_name,
                        confidence_scores=confidences
                    )
                    recommendation.problems.set(problems)

                    # Get current prediction count
                    prediction_count = PredictionHistory.objects.filter(
                        user=request.user
                    ).count()

                    # If we already have 5 predictions, delete the oldest one
                    if prediction_count >= 5:
                        oldest_prediction = PredictionHistory.objects.filter(
                            user=request.user
                        ).earliest('created_at')
                        oldest_prediction.delete()

                    # Save new prediction to history
                    problem_descriptions = [p.description for p in problems]
                    PredictionHistory.objects.create(
                        user=request.user,
                        car_type=car_type.name,
                        car_brand=car_brand.name,
                        problems=problem_descriptions,
                        predicted_services=predictions
                    )
                    
                    # Update usage count
                    usage.used_count += 1
                    usage.save()
                    
                    # Update remaining uses
                    remaining_uses = max(0, USAGE_LIMIT - usage.used_count)

                    # Get updated prediction history
                    prediction_history = PredictionHistory.objects.filter(
                        user=request.user
                    ).order_by('-created_at')[:5]
                    
                    # Prepare results for display
                    results = []
                    for i, problem in enumerate(problems):
                        results.append({
                            'problem': problem.description,
                            'service': predictions[i].replace('_', ' ').title(),
                            'description': descriptions[i],
                            'confidence': f"{confidences[i] * 100:.1f}"
                        })
                    
                    context.update({
                        'recommendation_result': True,
                        'car_brand': car_brand,
                        'car_type': car_type,
                        'results': results,
                        'remaining_uses': remaining_uses,
                        'recommendation': recommendation,
                        'prediction_history': prediction_history,
                        'disclaimer': """
                            Hasil diagnosa ini merupakan rekomendasi awal berdasarkan masalah yang dilaporkan. 
                            Untuk hasil yang lebih akurat, silakan konsultasikan dengan mekanik kami saat 
                            melakukan servis. Diagnosa akhir dapat berbeda setelah pemeriksaan langsung 
                            oleh mekanik."""
                    })
                    
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan dalam memproses rekomendasi: {str(e)}')
            
            context['form'] = form
        
        return render(request, 'reservasi/get_recommendation.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan sistem: {str(e)}')
        return redirect('home')
        
def get_service_description(service):
    """Return description for each service type"""
    descriptions = {
        'Isi ulang freon': 'Penambahan refrigeran R134a untuk meningkatkan performa pendinginan AC.',
        'Ganti kompresor': 'Penggantian komponen utama AC yang berfungsi memompa refrigeran.',
        'Bersihkan filter': 'Pembersihan filter AC untuk melancarkan aliran udara dan menghilangkan bau.',
        'Perbaiki kondensor': 'Perbaikan atau penggantian komponen yang berfungsi mendinginkan refrigeran.',
    }
    return descriptions.get(service, 'Silakan konsultasikan dengan mekanik kami.')


@login_required
def batalkan_reservasi(request, reservasi_id):
    try:
        # Get the specific reservation for the logged-in user
        reservasi = get_object_or_404(Reservasi, id=reservasi_id, user=request.user)
        
        # Check if reservation is already cancelled
        if reservasi.is_cancelled:
            messages.error(request, 'Reservasi ini telah dibatalkan sebelumnya.')
            return redirect('home')
            
        # Check if reservation is already completed
        if reservasi.status == 'Selesai':
            messages.error(request, 'Tidak dapat membatalkan reservasi yang telah selesai.')
            return redirect('home')
        
        if request.method == 'POST':
            try:
                reservasi.is_cancelled = True
                reservasi.status = 'Dibatalkan'
                reservasi.status_updated_at = timezone.now()  # Tambahkan ini
                reservasi.save()
                messages.success(request, 'Reservasi berhasil dibatalkan.')
                return redirect('home')
            except Exception as e:
                messages.error(request, f'Gagal membatalkan reservasi: {str(e)}')
                return redirect('home')
            
        return render(request, 'reservasi/batalkan_reservasi.html', {'reservasi': reservasi})
        
    except Http404:
        messages.error(request, 'Reservasi tidak ditemukan.')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('home')

@login_required
def export_recommendation_pdf(request, recommendation_id):
    recommendation = get_object_or_404(Recommendation, id=recommendation_id, user=request.user)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    elements.append(Paragraph("Laporan Rekomendasi Perawatan AC", title_style))
    
    # Car Info
    elements.append(Paragraph(f"Kendaraan: {recommendation.car_brand} - {recommendation.car_type}", styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    # Current date and time
    current_datetime = datetime.now()
    elements.append(Paragraph(f"Tanggal: {current_datetime.strftime('%d %B %Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Create a structured list of problems with their corresponding recommendations
    problems = recommendation.problems.all().order_by('id')  # Ensure consistent ordering
    recommended_services = recommendation.recommended_services
    service_descriptions = recommendation.service_descriptions
    
    # Create a list of problem-recommendation pairs
    recommendations_data = []
    for i, problem in enumerate(problems):
        if i < len(recommended_services) and i < len(service_descriptions):
            recommendations_data.append({
                'problem': problem,
                'service': recommended_services[i],
                'description': service_descriptions[i]
            })
    
    # Results - using the structured data
    for i, rec_data in enumerate(recommendations_data):
        elements.append(Paragraph(f"Masalah #{i+1}", styles['Heading3']))
        
        data = [
            ['Masalah:', rec_data['problem'].description],
            ['Rekomendasi:', rec_data['service'].replace('_', ' ').title()],
            ['Deskripsi:', rec_data['description']]
        ]
        
        t = Table(data, colWidths=[100, 400])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray
    )
    elements.append(Paragraph(
        """Hasil diagnosa ini merupakan rekomendasi awal berdasarkan masalah yang dilaporkan. 
        Untuk hasil yang lebih akurat, silakan konsultasikan dengan mekanik kami saat melakukan servis. 
        Diagnosa akhir dapat berbeda setelah pemeriksaan langsung oleh mekanik.""",
        disclaimer_style
    ))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"rekomendasi_ac_{current_datetime.strftime('%Y%m%d_%H%M%S')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)