from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse
from reservasi.models import Reservasi
from .forms import AdminLoginForm
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.shortcuts import render
from reservasi.forms import RecommendationForm
from reservasi.ml_service import recommender
from django.db import transaction
from django.db.models import Count
import seaborn as sns
from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
import json
from datetime import timedelta, datetime
import pytz
import matplotlib.pyplot as plt
import io
import base64
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.lib.colors import PCMYKColor
from django.db.models import Sum
import matplotlib
matplotlib.use('Agg')

def is_admin(user):
    """Check if user is authenticated and has staff privileges"""
    return user.is_authenticated and user.is_staff

def admin_login(request):
    """Handle admin login functionality"""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard:admin_dashboard')
    
    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None and user.is_staff:
                login(request, user)
                return redirect('admin_dashboard:admin_dashboard')
            else:
                messages.error(request, "Invalid username or password, or you don't have admin privileges.")
    else:
        form = AdminLoginForm()
    return render(request, 'dashboard/admin_login.html', {'form': form})

@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def admin_recommendation(request):
    """View for admin recommendation feature with detailed model performance metrics"""
    form = RecommendationForm()
    context = {'form': form}
    
    if request.method == 'POST':
        form = RecommendationForm(request.POST)
        if form.is_valid():
            try:
                # Get form data
                problems = form.cleaned_data['problems']
                car_type = form.cleaned_data['car_type']
                car_brand = form.cleaned_data['car_brand']
                
                # Create a list to store results with problem IDs
                results = []
                
                for problem in problems:
                    # Get prediction for current problem
                    prediction, confidence, model_performances = recommender.predict(
                        symptom=problem.description,
                        car_type=car_type.name,
                        car_brand=car_brand.name
                    )
                    
                    # Format model performances for this problem
                    formatted_performances = []
                    for name, metrics in model_performances.items():
                        # Create a unique identifier for the confusion matrix plot
                        confusion_matrix_id = f"matrix_{problem.id}_{name.replace(' ', '_')}"
                        
                        formatted_performances.append({
                            'name': name,
                            'cv_score': f"{metrics['cv_score']*100:.1f}",
                            'cv_std': f"{metrics['cv_std']*100:.1f}",
                            'train_score': f"{metrics['train_score']*100:.1f}",
                            'test_score': f"{metrics['test_score']*100:.1f}",
                            'precision': f"{metrics['classification_report']['macro avg']['precision']*100:.1f}",
                            'recall': f"{metrics['classification_report']['macro avg']['recall']*100:.1f}",
                            'f1_score': f"{metrics['classification_report']['macro avg']['f1-score']*100:.1f}",
                            'confusion_matrix_plot': metrics.get('confusion_matrix_plot', ''),
                            'confusion_matrix_id': confusion_matrix_id
                        })
                    
                    # Get service description
                    service_description = recommender.get_service_description(prediction)
                    
                    # Create result dictionary with problem ID
                    result = {
                        'problem_id': problem.id,
                        'problem': problem.description,
                        'service': prediction.replace('_', ' ').title(),
                        'description': service_description,
                        'confidence': f"{confidence*100:.1f}",
                        'model_performances': formatted_performances
                    }
                    
                    results.append(result)
                
                # Store results in session with problem IDs
                request.session['recommendation_results'] = []
                for result in results:
                    session_result = result.copy()
                    session_result['model_performances'] = [
                        {k: v for k, v in perf.items()}
                        for perf in result['model_performances']
                    ]
                    request.session['recommendation_results'].append(session_result)
                
                request.session['car_info'] = {
                    'brand': car_brand.name,
                    'type': car_type.name,
                    'timestamp': timezone.now().isoformat()
                }
                request.session.modified = True
                
                context.update({
                    'form': form,
                    'recommendation_result': True,
                    'results': results,
                    'car_info': f"{car_brand.name} - {car_type.name}"
                })
                
            except Exception as e:
                messages.error(request, f"Error generating recommendation: {str(e)}")
    
    return render(request, 'dashboard/admin_recommendation.html', context)

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard view with charts"""
    reservations = Reservasi.objects.filter(is_cancelled=False).order_by('-tanggal', '-waktu')
    
    # Get daily reservation data
    reservation_data = get_daily_reservations_data()
    
    context = {
        'reservations': reservations,
        'total_reservations': reservations.count(),
        'ongoing_repairs': reservations.filter(status='Dalam Perbaikan').count(),
        'completed_repairs': reservations.filter(status='Selesai').count(),
        'reservation_dates': json.dumps(reservation_data['dates']),
        'reservation_counts': json.dumps(reservation_data['counts']),
    }
    return render(request, 'dashboard/home.html', context)

def admin_logout(request):
    """Handle admin logout"""
    logout(request)
    return redirect('admin_dashboard:admin_login')

@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def mark_as_complete(request, reservation_id):
    """Mark a reservation as complete"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                reservation = get_object_or_404(Reservasi, id=reservation_id)
                
                if reservation.status != 'Dalam Perbaikan':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Reservasi ini tidak dalam status perbaikan.'
                    }, status=400)

                reservation.status = 'Selesai'
                reservation.completed_at = timezone.now()
                reservation.save()
                
                reservations = Reservasi.objects.filter(is_cancelled=False)
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Reservasi berhasil ditandai selesai.',
                    'total_reservations': reservations.count(),
                    'ongoing_repairs': reservations.filter(status='Dalam Perbaikan').count(),
                    'completed_repairs': reservations.filter(status='Selesai').count()
                })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Metode request tidak valid.'
    }, status=400)
    
@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def check_reservations(request):
    """Check and update reservations with chart data"""
    try:
        reservations = Reservasi.objects.filter(is_cancelled=False).order_by('-tanggal', '-waktu')
        reservation_html = render_to_string(
            'dashboard/_reservation_table.html',
            {'reservations': reservations},
            request=request
        )
        
        # Get updated chart data
        reservation_data = get_daily_reservations_data()
        
        data = {
            'reservation_html': reservation_html,
            'total_reservations': reservations.count(),
            'ongoing_repairs': reservations.filter(status='Dalam Perbaikan').count(),
            'completed_repairs': reservations.filter(status='Selesai').count(),
            'reservation_dates': json.dumps(reservation_data['dates']),
            'reservation_counts': json.dumps(reservation_data['counts'])
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def is_admin(user):
    """Check if user is authenticated and has staff privileges"""
    return user.is_authenticated and user.is_staff

@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def export_monthly_reservations(request):
    """Export monthly reservations as PDF with chart and payment summary"""
    try:
        # Get selected date from request or use current date
        selected_date_str = request.GET.get('selected_date')
        if selected_date_str:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m')
            year = selected_date.year
            month = selected_date.month
        else:
            current_date = timezone.now()
            year = current_date.year
            month = current_date.month
            
        # Get first and last day of selected month
        first_day = timezone.datetime(year, month, 1)
        if month == 12:
            last_day = timezone.datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = timezone.datetime(year, month + 1, 1) - timedelta(days=1)
            
        # Get reservation data for selected month
        reservations = Reservasi.objects.filter(
            is_cancelled=False,
            tanggal__gte=first_day,
            tanggal__lte=last_day
        ).order_by('-tanggal', '-waktu')
        
        # Create daily reservation data for chart
        daily_counts = (
            reservations
            .annotate(date=TruncDate('tanggal'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # Initialize data for all days in month
        date_dict = {(first_day + timedelta(days=x)).date(): 0 
                    for x in range((last_day - first_day).days + 1)}
        
        # Fill in actual counts
        for item in daily_counts:
            date_dict[item['date']] = item['count']
            
        dates = list(date_dict.keys())
        counts = list(date_dict.values())
        
        # Create matplotlib chart
        plt.figure(figsize=(10, 4))
        plt.plot(range(len(counts)), counts, marker='o')
        plt.title(f'Trend Pembuatan Reservasi Bulan {first_day.strftime("%B %Y")}')
        plt.xlabel('Tanggal')
        plt.ylabel('Jumlah Reservasi')
        
        # Set x-axis labels to show dates
        date_labels = [date.strftime('%d') for date in dates]
        plt.xticks(range(len(dates)), date_labels, rotation=45)
        plt.grid(True)
        plt.tight_layout()
        
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=16,
            spaceAfter=12,
            alignment=1
        )
        
        # PDF content
        pdf_content = []
        
        title = Paragraph(
            f"Laporan Reservasi Bengkel AC Mobil Central Cool<br/>{first_day.strftime('%B %Y')}", 
            title_style
        )
        pdf_content.append(title)
        pdf_content.append(Spacer(1, 12))
        
        # Add chart
        chart_image = Image(img_buffer, width=10*inch, height=4*inch)
        pdf_content.append(chart_image)
        pdf_content.append(Spacer(1, 12))
        
        # Calculate total payment
        total_payment = reservations.filter(
            status='Selesai',
            nominal_pembayaran__isnull=False
        ).aggregate(total=Sum('nominal_pembayaran'))['total'] or 0
        
        # Format total payment
        formatted_total = f"Rp {'{:,.0f}'.format(total_payment).replace(',', '.')}"
        
        # Summary statistics
        summary_text = Paragraph(
            f"Total Reservasi: {reservations.count()} | "
            f"Dalam Perbaikan: {reservations.filter(status='Dalam Perbaikan').count()} | "
            f"Selesai: {reservations.filter(status='Selesai').count()} | "
            f"Total Pembayaran: {formatted_total}",
            styles['Normal']
        )
        pdf_content.append(summary_text)
        pdf_content.append(Spacer(1, 12))
        
        # Create table data
        table_data = [
            ['Nama', 'No. Telepon', 'Tanggal', 'Waktu', 'Status', 'Pembayaran']
        ]
        
        total_payments = 0
        for reservasi in reservations:
            payment = ''
            if reservasi.status == 'Selesai' and reservasi.nominal_pembayaran:
                payment = f"Rp {'{:,.0f}'.format(reservasi.nominal_pembayaran).replace(',', '.')}"
                total_payments += reservasi.nominal_pembayaran
                
            table_data.append([
                str(reservasi.user.nama),
                str(reservasi.user.nomor_telepon),
                reservasi.tanggal.strftime("%d %B %Y"),
                reservasi.waktu.strftime("%H:%M"),
                reservasi.status,
                payment
            ])
        
        # Add total row
        table_data.append([
            'Total Pembayaran', '', '', '', '',
            f"Rp {'{:,.0f}'.format(total_payments).replace(',', '.')}"
        ])
        
        table = Table(table_data, colWidths=[150, 100, 100, 80, 80, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-2), colors.beige),
            ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (-1,1), (-1,-1), 'RIGHT'),
        ]))
        
        pdf_content.append(table)
        
        doc.build(pdf_content)
        
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="laporan_reservasi_{first_day.strftime("%B_%Y")}.pdf"'
        response.write(pdf)
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('admin_dashboard:admin_dashboard')

def get_daily_reservations_data(days=30):
    """Get reservation data for the last 30 days"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days-1)
    
    daily_counts = (
        Reservasi.objects
        .filter(
            tanggal__gte=start_date,
            tanggal__lte=end_date,
            is_cancelled=False
        )
        .annotate(date=TruncDate('tanggal'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Create a dict with all dates initialized to 0
    date_dict = {(start_date + timedelta(days=x)): 0 for x in range(days)}
    
    # Fill in actual counts
    for item in daily_counts:
        date_dict[item['date']] = item['count']
    
    # Convert to lists for Chart.js
    dates = list(date_dict.keys())
    counts = list(date_dict.values())
    
    return {
        'dates': [d.strftime('%Y-%m-%d') for d in dates],
        'counts': counts
    }

@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def edit_status(request, reservation_id):
    """Edit reservation status back to 'Dalam Perbaikan'"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                reservation = get_object_or_404(Reservasi, id=reservation_id)
                
                if reservation.status != 'Selesai':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Hanya reservasi dengan status Selesai yang dapat diedit.'
                    }, status=400)

                reservation.status = 'Dalam Perbaikan'
                reservation.completed_at = None
                reservation.save()
                
                reservations = Reservasi.objects.filter(is_cancelled=False)
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Status reservasi berhasil diubah menjadi Dalam Perbaikan.',
                    'total_reservations': reservations.count(),
                    'ongoing_repairs': reservations.filter(status='Dalam Perbaikan').count(),
                    'completed_repairs': reservations.filter(status='Selesai').count()
                })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Metode request tidak valid.'
    }, status=400)
    

@login_required
@user_passes_test(is_admin)
def update_payment(request, reservation_id):
    if request.method == 'POST':
        try:
            nominal = request.POST.get('nominal_pembayaran')
            if not nominal:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Nominal pembayaran tidak boleh kosong'
                }, status=400)

            try:
                nominal = float(nominal)
                if nominal <= 0:
                    raise ValueError()
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Nominal pembayaran harus berupa angka positif'
                }, status=400)

            with transaction.atomic():
                reservation = get_object_or_404(Reservasi, id=reservation_id)
                
                if reservation.status != 'Selesai':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Pembayaran hanya dapat diupdate untuk reservasi yang sudah selesai'
                    }, status=400)
                    
                reservation.nominal_pembayaran = nominal
                reservation.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Pembayaran berhasil diperbarui'
                })
                
        except Reservasi.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Reservasi tidak ditemukan'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

@login_required
@user_passes_test(is_admin, login_url='admin_dashboard:admin_login')
def export_recommendation_pdf(request):
    try:
        # Get results from session
        results = request.session.get('recommendation_results')
        car_info = request.session.get('car_info')
        
        if not results or not car_info:
            messages.error(request, 'Data rekomendasi tidak ditemukan. Silakan generate rekomendasi terlebih dahulu.')
            return redirect('admin_dashboard:admin_recommendation')

        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        # Initialize document elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=1
        )
        
        section_header = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading1'],
            fontSize=16,
            spaceBefore=15,
            spaceAfter=15,
            textColor=colors.HexColor('#2C3E50')
        )
        
        table_header = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            alignment=1
        )
        
        # Add title
        title = Paragraph("Laporan Diagnosa Teknis Servis AC", title_style)
        elements.append(title)
        
        # Add timestamp and car information
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(jakarta_tz)
        timestamp = current_time.strftime("%d %B %Y %H:%M WIB")
        
        # Convert month to Indonesian
        month_id = {
            'January': 'Januari',
            'February': 'Februari',
            'March': 'Maret',
            'April': 'April',
            'May': 'Mei',
            'June': 'Juni',
            'July': 'Juli',
            'August': 'Agustus',
            'September': 'September',
            'October': 'Oktober',
            'November': 'November',
            'December': 'Desember'
        }
        for eng, ind in month_id.items():
            timestamp = timestamp.replace(eng, ind)
        
        # Document metadata table
        header_info = [
            ['Waktu Diagnosa:', timestamp],
            ['Data Kendaraan:', f"{car_info['brand']} - {car_info['type']}"],
        ]
        
        header_table = Table(header_info, colWidths=[150, 400])
        header_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 30))
        
        # Process each prediction result
        for idx, result in enumerate(results, 1):
            # Section title for each analysis
            elements.append(Paragraph(f"Analisis Diagnosa #{idx}", section_header))
            elements.append(Spacer(1, 10))
            
            # Prediction details
            prediction_data = [
                ['Gejala/Masalah:', result['problem']],
                ['Rekomendasi Layanan:', result['service']],
                ['Tingkat Keyakinan:', f"{result['confidence']}%"],
                ['Deskripsi Layanan:', result['description']]
            ]
            
            pred_table = Table(prediction_data, colWidths=[150, 550])
            pred_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E9ECEF')),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(pred_table)
            elements.append(Spacer(1, 20))
            
            # Add model performance table
            if result.get('model_performances'):
                elements.append(Paragraph("Performa Model", section_header))
                elements.append(Spacer(1, 10))
                
                # Prepare header and data for performance table
                performance_header = [
                    'Model',
                    'Cross-validation Score',
                    'Training Accuracy',
                    'Testing Accuracy',
                    'Precision',
                    'Recall',
                    'F1-Score'
                ]
                
                performance_data = [performance_header]
                
                for perf in result['model_performances']:
                    row = [
                        perf['name'],
                        f"{perf['cv_score']}% ± {perf['cv_std']}%",
                        f"{perf['train_score']}%",
                        f"{perf['test_score']}%",
                        f"{perf['precision']}%",
                        f"{perf['recall']}%",
                        f"{perf['f1_score']}%"
                    ]
                    performance_data.append(row)
                
                # Create and style performance table
                col_widths = [120, 120, 100, 100, 80, 80, 80]
                perf_table = Table(performance_data, colWidths=col_widths)
                perf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('TOPPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(perf_table)
                elements.append(Spacer(1, 20))
            
                # Add confusion matrices
                elements.append(Paragraph("Visualisasi Confusion Matrix", section_header))
                elements.append(Spacer(1, 10))
                
                for perf in result['model_performances']:
                    if 'confusion_matrix_plot' in perf:
                        try:
                            img_data = base64.b64decode(perf['confusion_matrix_plot'])
                            img_buffer = BytesIO(img_data)
                            img = Image(img_buffer, width=300, height=300)
                            
                            matrix_title = Paragraph(
                                f"Confusion Matrix - {perf['name']}",
                                ParagraphStyle(
                                    'MatrixTitle',
                                    parent=styles['Normal'],
                                    fontSize=12,
                                    spaceAfter=10,
                                    alignment=1
                                )
                            )
                            elements.append(matrix_title)
                            elements.append(img)
                            elements.append(Spacer(1, 20))
                        except Exception as img_error:
                            print(f"Error processing confusion matrix image: {str(img_error)}")
                            continue
            
            # Add page break between analyses except for the last one
            if idx < len(results):
                elements.append(PageBreak())
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="laporan_diagnosa_teknis.pdf"'
        response.write(buffer.getvalue())
        buffer.close()
        
        # Clear session data
        try:
            del request.session['recommendation_results']
            del request.session['car_info']
            request.session.modified = True
        except KeyError:
            pass
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error dalam mengexport PDF: {str(e)}')
        return redirect('admin_dashboard:admin_recommendation')