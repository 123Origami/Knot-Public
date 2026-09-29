// item-detail.js
// Item detail page JavaScript

// Store data from Django template
var itemData = {};

// Set item data from global variable
function initItemData(data) {
    itemData = data || {};
    itemData.dailyRate = Number(itemData.dailyRate) || 0;
    itemData.depositAmount = Number(itemData.depositAmount) || 0;
    itemData.max_borrow_days = Number(itemData.max_borrow_days) || 14;
    if (!Array.isArray(itemData.unavailableDates)) {
        itemData.unavailableDates = [];
    }
}

// Get DOM elements
var startDateInput = null;
var endDateInput = null;
var bookingSummary = null;
var daysCountSpan = null;
var subtotalSpan = null;
var totalSpan = null;
var bookBtn = null;

// Set minimum date to today
var today = new Date().toISOString().split('T')[0];

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    startDateInput = document.getElementById('startDate');
    endDateInput = document.getElementById('endDate');
    bookingSummary = document.getElementById('bookingSummary');
    daysCountSpan = document.getElementById('daysCount');
    subtotalSpan = document.getElementById('subtotal');
    totalSpan = document.getElementById('total');
    bookBtn = document.getElementById('bookBtn');
    
    // Set min dates
    if (startDateInput) startDateInput.min = today;
    if (endDateInput) endDateInput.min = today;
    
    // Add event listeners
    if (startDateInput) startDateInput.addEventListener('change', updateBookingSummary);
    if (endDateInput) endDateInput.addEventListener('change', updateBookingSummary);
    
    // Booking form submit
    var bookingForm = document.getElementById('bookingForm');
    if (bookingForm) {
        bookingForm.addEventListener('submit', submitBooking);
    }
    
    // Thumbnail click handler
    var thumbnails = document.querySelectorAll('.thumbnail');
    var mainImage = document.querySelector('.main-image img');
    
    for (var i = 0; i < thumbnails.length; i++) {
        thumbnails[i].addEventListener('click', function() {
            // Remove active class from all thumbnails
            for (var j = 0; j < thumbnails.length; j++) {
                thumbnails[j].classList.remove('active');
            }
            // Add active class to clicked thumbnail
            this.classList.add('active');
            // Update main image
            var newImageUrl = this.getAttribute('data-image');
            if (mainImage) {
                mainImage.src = newImageUrl;
            }
        });
    }
    
    // Item review form submit (only rendered for completed returned bookings)
    var itemReviewForm = document.getElementById('itemReviewForm');
    if (itemReviewForm) {
        itemReviewForm.addEventListener('submit', submitItemReview);
    }
});

function updateBookingSummary() {
    if (!startDateInput || !endDateInput) return;
    
    var start = startDateInput.value;
    var end = endDateInput.value;
    
    if (!start || !end) {
        if (bookingSummary) bookingSummary.style.display = 'none';
        return;
    }
    
    var startDate = new Date(start);
    var endDate = new Date(end);
    var todayDate = new Date(today);
    todayDate.setHours(0, 0, 0, 0);
    startDate.setHours(0, 0, 0, 0);
    endDate.setHours(0, 0, 0, 0);

    if (startDate < todayDate || endDate < todayDate) {
        alert('Past dates cannot be booked');
        if (bookingSummary) bookingSummary.style.display = 'none';
        return;
    }
    
    if (endDate < startDate) {
        alert('End date cannot be before start date');
        if (bookingSummary) bookingSummary.style.display = 'none';
        return;
    }

    var days = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;
    if (days > itemData.max_borrow_days) {
        alert('This item can only be booked for up to ' + itemData.max_borrow_days + ' days.');
        if (bookingSummary) bookingSummary.style.display = 'none';
        return;
    }
    
    // Check availability
    if (isDateRangeUnavailable(startDate, endDate)) {
        alert('Selected dates are not available. Please choose different dates.');
        if (bookingSummary) bookingSummary.style.display = 'none';
        return;
    }
    
    var subtotal = days * itemData.dailyRate;
    var total = subtotal + itemData.depositAmount;
    
    if (daysCountSpan) daysCountSpan.textContent = days;
    if (subtotalSpan) subtotalSpan.textContent = 'Ksh ' + formatNumber(subtotal);
    if (totalSpan) totalSpan.textContent = 'Ksh ' + formatNumber(total);
    if (bookingSummary) bookingSummary.style.display = 'block';
}

function isDateRangeUnavailable(startDate, endDate) {
    var current = new Date(startDate);
    while (current <= endDate) {
        var dateStr = current.toISOString().split('T')[0];
        if (itemData.unavailableDates && itemData.unavailableDates.indexOf(dateStr) !== -1) {
            return true;
        }
        current.setDate(current.getDate() + 1);
    }
    return false;
}

async function submitBooking(event) {
    event.preventDefault();
    
    var startDate = startDateInput ? startDateInput.value : null;
    var endDate = endDateInput ? endDateInput.value : null;
    
    if (!startDate || !endDate) {
        alert('Please select start and end dates');
        return;
    }

    var bookingForm = document.getElementById('bookingForm');
    var hiddenItemIdInput = document.getElementById('itemId');
    var fallbackItemId = hiddenItemIdInput ? Number(hiddenItemIdInput.value) : 0;
    if (!fallbackItemId && bookingForm && bookingForm.dataset.itemId) {
        fallbackItemId = Number(bookingForm.dataset.itemId);
    }

    var itemId = Number(itemData.id) || fallbackItemId;

    if (!itemId) {
        alert('Missing required fields: item_id. Please refresh and try again.');
        return;
    }

    var startDateObj = new Date(startDate);
    var endDateObj = new Date(endDate);
    var todayDate = new Date(today);
    todayDate.setHours(0, 0, 0, 0);
    startDateObj.setHours(0, 0, 0, 0);
    endDateObj.setHours(0, 0, 0, 0);

    if (startDateObj < todayDate || endDateObj < todayDate) {
        alert('Past dates cannot be booked.');
        return;
    }

    if (endDateObj < startDateObj) {
        alert('End date cannot be before start date.');
        return;
    }

    var requestedDays = Math.ceil((endDateObj - startDateObj) / (1000 * 60 * 60 * 24)) + 1;
    if (requestedDays > itemData.max_borrow_days) {
        alert('This item can only be booked for up to ' + itemData.max_borrow_days + ' days.');
        return;
    }
    
    if (bookBtn) {
        bookBtn.disabled = true;
        bookBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    }
    
    try {
        var response = await fetch('/api/bookings/create/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                item_id: itemId,
                start_date: startDate,
                end_date: endDate
            })
        });
        
        var data = await response.json();
        
        if (response.ok) {
            alert('Booking request sent! The steward will review your request.');
            window.location.href = '/dashboard/';
        } else {
            alert(data.error || 'Booking failed. Please try again.');
            if (bookBtn) {
                bookBtn.disabled = false;
                bookBtn.innerHTML = '<i class="fas fa-calendar-check"></i> Request Booking';
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to create booking. Please try again.');
        if (bookBtn) {
            bookBtn.disabled = false;
            bookBtn.innerHTML = '<i class="fas fa-calendar-check"></i> Request Booking';
        }
    }
}

async function submitItemReview(event) {
    event.preventDefault();

    var bookingIdInput = document.getElementById('itemReviewBookingId');
    var reviewTypeInput = document.getElementById('itemReviewType');
    var ratingInput = document.getElementById('itemReviewRating');
    var commentInput = document.getElementById('itemReviewComment');
    var submitBtn = document.getElementById('submitItemReviewBtn');

    if (!bookingIdInput || !reviewTypeInput || !ratingInput || !commentInput) {
        alert('Review form is not available right now.');
        return;
    }

    var payload = {
        booking: Number(bookingIdInput.value),
        review_type: reviewTypeInput.value,
        rating: Number(ratingInput.value),
        comment: commentInput.value.trim()
    };

    if (!payload.booking || !payload.rating || !payload.comment) {
        alert('Please complete rating and comment before submitting your review.');
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    }

    try {
        var response = await fetch('/api/reviews/reviews/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        });

        var data = await response.json();

        if (!response.ok) {
            var message = data.detail || data.non_field_errors || data.error || 'Could not submit review.';
            if (Array.isArray(message)) {
                message = message[0];
            }
            throw new Error(message);
        }

        alert('Review submitted successfully.');
        window.location.reload();
    } catch (error) {
        alert(error.message || 'Could not submit review.');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-star"></i> Submit Review';
        }
    }
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}