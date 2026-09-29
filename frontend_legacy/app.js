// DOM Elements
const planningForm = document.getElementById('planning-form');
const budgetSlider = document.getElementById('total_budget_slider');
const budgetHidden = document.getElementById('total_budget');
const interestChipsContainer = document.getElementById('interest-chips-container');
const interestsHidden = document.getElementById('interests');
const aiChooseDestToggle = document.getElementById('ai_choose_destination');
const destinationInput = document.getElementById('destination');
const submitButton = document.getElementById('submit-button');

// Main Section Panels
const inputSection = document.getElementById('input-section');
const workflowSection = document.getElementById('workflow-section');
const reviewPlanSection = document.getElementById('review-plan-section');
const passengerSection = document.getElementById('passenger-section');
const confirmationSection = document.getElementById('confirmation-section');
const dashboardSection = document.getElementById('dashboard-section');
const terminalBody = document.getElementById('terminal-body');

// Navigation & Flow Action Buttons
const btnContinueToBooking = document.getElementById('btn-continue-to-booking');
const btnReviewBackToInput = document.getElementById('btn-review-back-to-input');
const passengerBookingForm = document.getElementById('passenger-booking-form');
const btnBackToReview = document.getElementById('btn-back-to-review');
const btnConfirmMockBooking = document.getElementById('btn-confirm-mock-booking');
const btnGenerateFinalReport = document.getElementById('btn-generate-final-report');

// Dashboard Tabs & Actions
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const restartBtn = document.getElementById('restart-btn');
const downloadBtn = document.getElementById('download-btn');

// State Variables
let selectedInterests = ['Nature'];
let activeJobId = null;
let pollInterval = null;
let renderedLogCount = 0;
let travelPlanResult = null;
let bookingConfirmationData = null;
let budgetChart = null;

// Initialize Flatpickr Calendar
flatpickr("#date_range_picker", {
    mode: "range",
    dateFormat: "Y-m-d",
    minDate: "today",
    onChange: function(selectedDates, dateStr, instance) {
        if (selectedDates.length === 2) {
            const s = flatpickr.formatDate(selectedDates[0], "Y-m-d");
            const e = flatpickr.formatDate(selectedDates[1], "Y-m-d");
            document.getElementById('start_date').value = s;
            document.getElementById('end_date').value = e;
            const formatDate = (date) => {
                return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
            };
            document.getElementById('travel_dates').value = `${formatDate(selectedDates[0])} to ${formatDate(selectedDates[1])}`;
        } else {
            document.getElementById('start_date').value = "";
            document.getElementById('end_date').value = "";
            document.getElementById('travel_dates').value = "";
        }
    }
});

const budgetInput = document.getElementById('total_budget_input');

// Initialize Slider and Input Link
budgetSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    budgetInput.value = val;
    budgetHidden.value = val;
});

budgetInput.addEventListener('input', (e) => {
    let val = parseInt(e.target.value);
    if (isNaN(val)) val = 1000;
    if (val < 1000) val = 1000;
    if (val > 500000) val = 500000;
    
    budgetSlider.value = val;
    budgetHidden.value = val;
});

// Handle AI Choose Destination Toggle
aiChooseDestToggle.addEventListener('change', (e) => {
    if (e.target.checked) {
        destinationInput.value = "";
        destinationInput.placeholder = "AI will select the best place";
        destinationInput.disabled = true;
    } else {
        destinationInput.placeholder = "e.g., Goa, Munnar, Manali";
        destinationInput.disabled = false;
    }
});

// Handle Interest Chips selection
interestChipsContainer.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    
    const value = chip.getAttribute('data-value');
    
    if (chip.classList.contains('active')) {
        if (selectedInterests.length > 1) {
            chip.classList.remove('active');
            selectedInterests = selectedInterests.filter(i => i !== value);
        }
    } else {
        chip.classList.add('active');
        selectedInterests.push(value);
    }
    
    interestsHidden.value = selectedInterests.join(', ');
});

// Handle Tab Switching
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        
        tabButtons.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        
        btn.classList.add('active');
        const targetEl = document.getElementById(targetTab);
        if (targetEl) targetEl.classList.add('active');
    });
});

// Reset and Return to Planning Form
restartBtn.addEventListener('click', () => {
    activeJobId = null;
    renderedLogCount = 0;
    travelPlanResult = null;
    bookingConfirmationData = null;
    terminalBody.innerHTML = '';
    
    document.querySelectorAll('.step-card').forEach(card => {
        card.className = 'step-card';
        const icon = card.querySelector('.step-status i');
        if (icon) icon.className = 'fa-solid fa-circle';
    });
    
    dashboardSection.classList.add('hidden');
    confirmationSection.classList.add('hidden');
    passengerSection.classList.add('hidden');
    reviewPlanSection.classList.add('hidden');
    workflowSection.classList.add('hidden');
    inputSection.classList.remove('hidden');
    
    submitButton.disabled = false;
    submitButton.innerHTML = '<span>Begin Agent Kickoff</span><i class="fa-solid fa-arrow-right"></i>';
});

// Helper to switch visible panel
function showPanel(panelToShow) {
    [inputSection, workflowSection, reviewPlanSection, passengerSection, confirmationSection, dashboardSection].forEach(p => {
        if (p) p.classList.add('hidden');
    });
    if (panelToShow) panelToShow.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 1. Submit Initial Planning Form to API
planningForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const startDateStr = document.getElementById('start_date').value;
    const endDateStr = document.getElementById('end_date').value;
    
    if (!startDateStr || !endDateStr) {
        alert("Please select both start and end travel dates.");
        return;
    }
    
    const startDateObj = new Date(startDateStr);
    const endDateObj = new Date(endDateStr);
    
    if (endDateObj < startDateObj) {
        alert("End date cannot be before start date.");
        return;
    }
    
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    };
    
    const formattedDates = `${formatDate(startDateStr)} to ${formatDate(endDateStr)}`;
    const diffTime = Math.abs(endDateObj - startDateObj);
    const calculatedNights = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    const data = {
        starting_location: document.getElementById('starting_location').value.trim(),
        destination: document.getElementById('destination').value.trim(),
        travel_dates: formattedDates,
        num_travellers: parseInt(document.getElementById('num_travellers').value),
        total_budget: parseFloat(document.getElementById('total_budget').value),
        interests: interestsHidden.value,
        hotel_type: document.getElementById('hotel_type').value,
        transport_preferences: document.getElementById('transport_preferences').value,
        additional_requirements: document.getElementById('additional_requirements').value.trim(),
        trip_type: document.getElementById('trip_type').value,
        ai_choose_destination: aiChooseDestToggle.checked,
        nights: calculatedNights
    };
    
    if (!data.ai_choose_destination && !data.destination) {
        alert("Please enter a destination or select 'AI Choose'.");
        return;
    }
    
    submitButton.disabled = true;
    submitButton.innerHTML = '<span>Connecting to Crew...</span><i class="fa-solid fa-circle-notch fa-spin"></i>';
    
    try {
        const response = await fetch('/api/plan-trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`Server returned code ${response.status}`);
        }
        
        const resData = await response.json();
        activeJobId = resData.job_id;
        
        showPanel(workflowSection);
        
        renderedLogCount = 0;
        pollInterval = setInterval(pollJobStatus, 1000);
        
    } catch (err) {
        console.error(err);
        alert(`Failed to start trip planning. Error: ${err.message}`);
        submitButton.disabled = false;
        submitButton.innerHTML = '<span>Begin Agent Kickoff</span><i class="fa-solid fa-arrow-right"></i>';
    }
});

// Poll Status from FastAPI
async function pollJobStatus() {
    if (!activeJobId) return;
    
    try {
        const response = await fetch(`/api/plan-trip/status/${activeJobId}`);
        if (!response.ok) throw new Error("Status endpoint error");
        
        const job = await response.json();
        
        if (job.logs && job.logs.length > renderedLogCount) {
            for (let i = renderedLogCount; i < job.logs.length; i++) {
                appendTerminalLine(job.logs[i]);
            }
            renderedLogCount = job.logs.length;
        }
        
        updateWorkflowVisualSteps(job.current_step);
        
        if (job.status === 'success') {
            clearInterval(pollInterval);
            travelPlanResult = job.result;
            
            // Present Plan Review Section (Human Approval step)
            setTimeout(() => {
                populatePlanReview(travelPlanResult);
                showPanel(reviewPlanSection);
            }, 1000);
            
        } else if (job.status === 'failed') {
            clearInterval(pollInterval);
            appendTerminalLine("ERROR: CrewAI flow aborted due to a step exception.", "error");
            alert("Planning task failed. Please check terminal logs for details.");
        }
        
    } catch (err) {
        console.error("Polling error:", err);
    }
}

function appendTerminalLine(text, type = "info") {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    line.innerHTML = `
        <span class="term-time">[${time}]</span>
        <span class="term-text">${text}</span>
    `;
    
    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
}

const STEP_ORDER = [
    'trip_intake',
    'destination_selection',
    'flight_hotel_search',
    'budget_optimization',
    'replan_budget',
    'itinerary_planning',
    'supervisor_validation',
    'report_compilation',
    'completed'
];

function updateWorkflowVisualSteps(currentStepName) {
    let currentIdx = STEP_ORDER.indexOf(currentStepName);
    if (currentIdx === -1) currentIdx = 0;
    
    document.querySelectorAll('.step-card').forEach(card => {
        const stepName = card.getAttribute('data-step');
        const stepIdx = STEP_ORDER.indexOf(stepName);
        const icon = card.querySelector('.step-status i');
        
        if (stepIdx < currentIdx || currentStepName === 'completed') {
            card.className = 'step-card completed';
            icon.className = 'fa-solid fa-circle-check';
        } else if (stepIdx === currentIdx) {
            card.className = 'step-card active';
            icon.className = 'fa-solid fa-circle-notch fa-spin';
        } else {
            card.className = 'step-card';
            icon.className = 'fa-solid fa-circle';
        }
    });
}

// 2. Populate Plan Review (Human Approval)
function populatePlanReview(result) {
    if (!result) return;
    
    const dest = result.destination || 'Destination';
    const dates = result.travel_dates || 'Selected Dates';
    const pax = result.num_travellers || 1;
    
    document.getElementById('review-dest-name').textContent = dest;
    document.getElementById('review-destination-title').textContent = `Travel Plan for ${dest}`;
    document.getElementById('review-dates-text').textContent = `${dates} (${pax} Pax)`;
    
    const flight = result.flight || {};
    const hotel = result.hotel || {};
    
    const opText = (flight.operator || '').toLowerCase();
    const modeText = (flight.mode || '').toLowerCase();
    const prefText = (result.transport_preferences || '').toLowerCase();
    const combined = `${opText} ${modeText} ${prefText}`;
    
    const transportIcon = document.getElementById('review-transport-icon');
    if (transportIcon) {
        if (combined.includes('train') || combined.includes('rail') || combined.includes('express')) {
            transportIcon.className = 'fa-solid fa-train';
        } else if (combined.includes('bus') || combined.includes('volvo') || combined.includes('ksrtc')) {
            transportIcon.className = 'fa-solid fa-bus';
        } else if (combined.includes('flight') || combined.includes('air')) {
            transportIcon.className = 'fa-solid fa-plane';
        } else if (combined.includes('cab') || combined.includes('taxi') || combined.includes('car')) {
            transportIcon.className = 'fa-solid fa-car';
        } else {
            transportIcon.className = 'fa-solid fa-route';
        }
    }
    
    document.getElementById('review-flight-name').textContent = flight.operator ? `${flight.operator} (${flight.class || 'Standard'})` : 'Regional Transit';
    const flightPrice = flight.price_per_person ? flight.price_per_person * pax : (flight.total_price || 0);
    document.getElementById('review-flight-cost').textContent = `INR ${Number(flightPrice).toLocaleString('en-IN')}`;
    
    document.getElementById('review-hotel-name').textContent = hotel.name || 'Selected Lodging';
    document.getElementById('review-hotel-cost').textContent = `INR ${(hotel.total_cost || 0).toLocaleString('en-IN')}`;
    
    document.getElementById('review-total-cost').textContent = `INR ${(result.total_cost || 0).toLocaleString('en-IN')}`;
    document.getElementById('review-budget-status').textContent = result.is_replanned ? 'Optimized within Limit' : 'Within Target Budget';
}

// Button: Back from Review to Input
if (btnReviewBackToInput) {
    btnReviewBackToInput.addEventListener('click', () => {
        showPanel(inputSection);
        submitButton.disabled = false;
        submitButton.innerHTML = '<span>Begin Agent Kickoff</span><i class="fa-solid fa-arrow-right"></i>';
    });
}

// 3. Human Approval -> Continue to Passenger Details
if (btnContinueToBooking) {
    btnContinueToBooking.addEventListener('click', () => {
        setupPassengerDetailsPage();
        showPanel(passengerSection);
    });
}

// Setup Dynamic Traveller Forms
function setupPassengerDetailsPage() {
    const numTravellers = travelPlanResult ? (travelPlanResult.num_travellers || 1) : 1;
    const countBadge = document.getElementById('traveller-count-badge');
    if (countBadge) countBadge.textContent = `${numTravellers} ${numTravellers > 1 ? 'Travellers' : 'Traveller'}`;
    
    const container = document.getElementById('dynamic-travellers-container');
    if (!container) return;
    container.innerHTML = '';
    
    for (let i = 1; i <= numTravellers; i++) {
        const card = document.createElement('div');
        card.className = 'traveller-card';
        card.innerHTML = `
            <div class="traveller-card-title">
                <span class="traveller-num-badge">${i}</span>
                <span>Traveller ${i} Information</span>
            </div>
            <div class="form-row">
                <div class="form-group col-4">
                    <label for="traveller_name_${i}">Full Name</label>
                    <div class="input-icon-wrap">
                        <i class="fa-solid fa-user field-icon"></i>
                        <input type="text" id="traveller_name_${i}" class="traveller-name-input" placeholder="e.g., Alex Johnson" required value="${i === 1 ? 'Alex Johnson' : (i === 2 ? 'Jordan Smith' : `Traveller ${i}`)}">
                    </div>
                </div>
                <div class="form-group col-2">
                    <label for="traveller_age_${i}">Age</label>
                    <div class="input-icon-wrap">
                        <i class="fa-solid fa-hourglass-half field-icon"></i>
                        <input type="number" id="traveller_age_${i}" class="traveller-age-input" min="1" max="120" value="${25 + (i * 3)}" required>
                    </div>
                </div>
                <div class="form-group col-3">
                    <label for="traveller_gender_${i}">Gender</label>
                    <div class="input-icon-wrap">
                        <i class="fa-solid fa-venus-mars field-icon"></i>
                        <select id="traveller_gender_${i}" class="traveller-gender-input" required>
                            <option value="Male" ${i % 2 === 1 ? 'selected' : ''}>Male</option>
                            <option value="Female" ${i % 2 === 0 ? 'selected' : ''}>Female</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                </div>
                <div class="form-group col-3">
                    <label for="traveller_id_${i}">ID / Passport</label>
                    <div class="input-icon-wrap">
                        <i class="fa-solid fa-passport field-icon"></i>
                        <input type="text" id="traveller_id_${i}" class="traveller-id-input" placeholder="e.g., ID-89420" required value="IND-${78200 + i * 15}">
                    </div>
                </div>
            </div>
        `;
        container.appendChild(card);
    }
    
    // Default primary contact
    const contactName = document.getElementById('contact_name');
    if (contactName && !contactName.value) contactName.value = 'Alex Johnson';
    const contactEmail = document.getElementById('contact_email');
    if (contactEmail && !contactEmail.value) contactEmail.value = 'alex.johnson@example.com';
    const contactPhone = document.getElementById('contact_phone');
    if (contactPhone && !contactPhone.value) contactPhone.value = '+91 98765 43210';
    
    // Live update virtual card preview
    initVirtualCardSync();
}

function initVirtualCardSync() {
    const cardHolderInput = document.getElementById('mock_cardholder');
    const cardNumInput = document.getElementById('mock_cardnum');
    const expiryInput = document.getElementById('mock_expiry');
    
    const dispHolder = document.getElementById('vc-display-holder');
    const dispNum = document.getElementById('vc-display-number');
    const dispExpiry = document.getElementById('vc-display-expiry');
    
    if (cardHolderInput && dispHolder) {
        cardHolderInput.addEventListener('input', () => {
            dispHolder.textContent = cardHolderInput.value.trim() || 'Alex Johnson';
        });
    }
    if (cardNumInput && dispNum) {
        cardNumInput.addEventListener('input', () => {
            const raw = cardNumInput.value.replace(/\s+/g, '');
            if (raw.length >= 4) {
                dispNum.textContent = raw.match(/.{1,4}/g)?.join(' ') || cardNumInput.value;
            } else {
                dispNum.textContent = cardNumInput.value || '4532 •••• •••• 8821';
            }
        });
    }
    if (expiryInput && dispExpiry) {
        expiryInput.addEventListener('input', () => {
            dispExpiry.textContent = expiryInput.value.trim() || '12/28';
        });
    }
}

if (btnBackToReview) {
    btnBackToReview.addEventListener('click', () => {
        showPanel(reviewPlanSection);
    });
}

// 4. Submit Passenger Details -> Trigger Mock Booking Agent
if (passengerBookingForm) {
    passengerBookingForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!activeJobId || !travelPlanResult) {
            alert("No active trip session. Please restart planning.");
            return;
        }
        
        const numTravellers = travelPlanResult.num_travellers || 1;
        const travellersList = [];
        
        for (let i = 1; i <= numTravellers; i++) {
            const name = document.getElementById(`traveller_name_${i}`)?.value.trim() || `Traveller ${i}`;
            const age = parseInt(document.getElementById(`traveller_age_${i}`)?.value) || 28;
            const gender = document.getElementById(`traveller_gender_${i}`)?.value || 'Male';
            const idNumber = document.getElementById(`traveller_id_${i}`)?.value.trim() || 'Verified';
            
            travellersList.push({
                name: name,
                age: age,
                gender: gender,
                id_number: idNumber
            });
        }
        
        const bookingPayload = {
            job_id: activeJobId,
            primary_contact: {
                name: document.getElementById('contact_name')?.value.trim() || travellersList[0].name,
                email: document.getElementById('contact_email')?.value.trim() || 'traveler@example.com',
                phone: document.getElementById('contact_phone')?.value.trim() || '+91 98765 43210'
            },
            travellers: travellersList,
            mock_payment: {
                cardholder: document.getElementById('mock_cardholder')?.value.trim() || 'Alex Johnson',
                card_number: document.getElementById('mock_cardnum')?.value.trim() || '4532 •••• •••• 8821',
                expiry: document.getElementById('mock_expiry')?.value.trim() || '12/28',
                cvv: document.getElementById('mock_cvv')?.value.trim() || '888'
            }
        };
        
        btnConfirmMockBooking.disabled = true;
        btnConfirmMockBooking.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Mock Booking Agent Processing...';
        
        try {
            const response = await fetch('/api/process-mock-booking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bookingPayload)
            });
            
            if (!response.ok) throw new Error("Mock booking processing failed");
            
            bookingConfirmationData = await response.json();
            
            // Populate Confirmation Page
            populateConfirmationPage(bookingConfirmationData);
            showPanel(confirmationSection);
            
        } catch (err) {
            console.error("Booking error:", err);
            alert(`Mock booking failed: ${err.message}`);
        } finally {
            btnConfirmMockBooking.disabled = false;
            btnConfirmMockBooking.innerHTML = '<i class="fa-solid fa-lock"></i> Confirm Mock Booking';
        }
    });
}

// 5. Populate Mock Booking Confirmation Page
function populateConfirmationPage(data) {
    if (!data) return;
    
    // Transport Booking Card (Flight / Train / Bus / Cab / Generic)
    const transportCard = document.getElementById('conf-flight-card');
    const tb = data.transport_booking || data.flight_booking;
    
    if (tb && transportCard && tb.price > 0) {
        transportCard.classList.remove('hidden');
        
        const mode = tb.mode || (tb.booking_id && tb.booking_id.startsWith('TRN') ? 'Train' : 
                     (tb.booking_id && tb.booking_id.startsWith('BUS') ? 'Bus' : 
                     (tb.booking_id && tb.booking_id.startsWith('CAB') ? 'Cab' : 
                     (tb.booking_id && tb.booking_id.startsWith('FLY') ? 'Flight' : 'Transport'))));
        
        const iconElem = document.getElementById('conf-transport-icon');
        const titleElem = document.getElementById('conf-transport-title');
        const routeIconElem = document.getElementById('conf-route-arrow-icon');
        
        let iconClass = 'fa-solid fa-route';
        let routeIconClass = 'fa-solid fa-arrow-right-long';
        
        if (mode.toLowerCase().includes('train')) {
            iconClass = 'fa-solid fa-train';
            routeIconClass = 'fa-solid fa-train';
        } else if (mode.toLowerCase().includes('bus')) {
            iconClass = 'fa-solid fa-bus';
            routeIconClass = 'fa-solid fa-bus';
        } else if (mode.toLowerCase().includes('flight')) {
            iconClass = 'fa-solid fa-plane-departure';
            routeIconClass = 'fa-solid fa-plane';
        } else if (mode.toLowerCase().includes('cab') || mode.toLowerCase().includes('car')) {
            iconClass = 'fa-solid fa-car';
            routeIconClass = 'fa-solid fa-car';
        }
        
        if (iconElem) iconElem.className = iconClass;
        if (titleElem) titleElem.textContent = `${mode} Booking`;
        if (routeIconElem) routeIconElem.className = routeIconClass;
        
        document.getElementById('conf-flight-pnr').textContent = tb.booking_id || `${mode.substring(0, 3).toUpperCase()}-2026-CONFIRMED`;
        document.getElementById('conf-flight-airline').textContent = tb.operator || tb.airline || `${mode} Service`;
        document.getElementById('conf-flight-num').textContent = tb.service_number || tb.flight_number || 'TR-101';
        document.getElementById('conf-flight-from').textContent = tb.from_location || 'Origin';
        document.getElementById('conf-flight-to').textContent = tb.to_location || 'Destination';
        document.getElementById('conf-flight-dept-time').textContent = tb.departure_time || '08:00';
        document.getElementById('conf-flight-arr-time').textContent = tb.arrival_time || '11:30';
        document.getElementById('conf-flight-date').textContent = tb.departure_date || 'Travel Date';
        document.getElementById('conf-flight-pax').textContent = `${tb.num_travellers || 1} Pax`;
        document.getElementById('conf-flight-price').textContent = `INR ${Number(tb.price || 0).toLocaleString('en-IN')}`;
    } else if (transportCard) {
        transportCard.classList.add('hidden');
    }
    
    // Accommodation Booking Card (Show only if accommodation required)
    const hotelCard = document.getElementById('conf-hotel-card');
    if (data.accommodation_booking && data.accommodation_booking.price > 0 && hotelCard) {
        hotelCard.classList.remove('hidden');
        const hb = data.accommodation_booking;
        document.getElementById('conf-hotel-pnr').textContent = hb.booking_id || 'HTL-2026-CONFIRMED';
        document.getElementById('conf-hotel-name').textContent = hb.hotel_name || 'Selected Resort';
        document.getElementById('conf-hotel-location').innerHTML = `<i class="fa-solid fa-location-dot"></i> ${hb.location || 'Prime Location'}`;
        document.getElementById('conf-hotel-dates').textContent = `${hb.check_in || ''} - ${hb.check_out || ''}`;
        document.getElementById('conf-hotel-rooms').textContent = `${hb.rooms || 1} Room(s), ${hb.guests || 1} Guest(s)`;
        document.getElementById('conf-hotel-price').textContent = `INR ${Number(hb.price || 0).toLocaleString('en-IN')}`;
    } else if (hotelCard) {
        hotelCard.classList.add('hidden');
    }
    
    // Summary Fields
    const namesList = data.traveller_names ? data.traveller_names.join(', ') : 'Registered Travellers';
    document.getElementById('conf-travellers-list').textContent = namesList;
    document.getElementById('conf-booking-date').textContent = data.booking_date || 'October 01, 2026';
    document.getElementById('conf-total-amount').textContent = `INR ${Number(data.total_booked_amount || 0).toLocaleString('en-IN')}`;
}

// 6. Generate Final Report -> Trigger Report Compiler Agent
if (btnGenerateFinalReport) {
    btnGenerateFinalReport.addEventListener('click', async () => {
        if (!activeJobId) {
            alert("No active session.");
            return;
        }
        
        btnGenerateFinalReport.disabled = true;
        btnGenerateFinalReport.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Compiling Final Travel Dossier...';
        
        try {
            const response = await fetch('/api/compile-final-report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ job_id: activeJobId })
            });
            
            if (!response.ok) throw new Error("Report compilation failed");
            
            const res = await response.json();
            travelPlanResult = res.result;
            if (res.booking_confirmation) {
                bookingConfirmationData = res.booking_confirmation;
            }
            
            // Render Final Travel Report Dashboard
            renderTravelPlan(travelPlanResult, bookingConfirmationData);
            showPanel(dashboardSection);
            
        } catch (err) {
            console.error("Report compilation error:", err);
            alert(`Failed to compile final report: ${err.message}`);
        } finally {
            btnGenerateFinalReport.disabled = false;
            btnGenerateFinalReport.innerHTML = '<i class="fa-solid fa-file-invoice"></i> Generate Final Report';
        }
    });
}

// Render Planning outputs onto Final Dashboard
function renderTravelPlan(result, bookingData = null) {
    if (!result) return;
    
    const destName = result.destination || 'Destination';
    document.getElementById('summary-destination').textContent = `Trip to ${destName}`;
    
    const dateVal = result.travel_dates || 'Upcoming Journey';
    const paxVal = result.num_travellers || 1;
    
    document.getElementById('summary-dates').innerHTML = `<i class="fa-solid fa-calendar"></i> ${dateVal}`;
    document.getElementById('summary-pax').innerHTML = `<i class="fa-solid fa-users"></i> ${paxVal} Pax`;
    
    const budgetBadge = document.getElementById('summary-budget-badge');
    if (budgetBadge) {
        if (result.is_replanned) {
            budgetBadge.className = 'badge-pill';
            budgetBadge.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
            budgetBadge.style.color = 'var(--accent-yellow)';
            budgetBadge.style.borderColor = 'rgba(245, 158, 11, 0.2)';
            budgetBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Optimized within Budget`;
        } else {
            budgetBadge.className = 'badge-pill badge-budget-status';
            budgetBadge.style.backgroundColor = '';
            budgetBadge.style.color = '';
            budgetBadge.style.borderColor = '';
            budgetBadge.innerHTML = `<i class="fa-solid fa-check"></i> Within Budget`;
        }
    }

    // 1b. Overview Summary Text Card on Final Page
    const summaryTextEl = document.getElementById('dashboard-summary-text');
    if (summaryTextEl) {
        let narrative = '';
        if (result.rationale) {
            narrative += `<strong>Destination Rationale:</strong> ${result.rationale} <br><br>`;
        }
        const totalFormatted = result.total_cost ? Number(result.total_cost).toLocaleString('en-IN') : '0';
        narrative += `This finalized itinerary for <strong>${destName}</strong> covers <strong>${dateVal}</strong> for <strong>${paxVal} traveler(s)</strong> with an estimated total cost of <strong>INR ${totalFormatted}</strong> (${result.is_replanned ? 'optimized within your limit' : 'within target budget'}). Mock reservations are confirmed for <em>${result.hotel?.name || 'Selected Accommodation'}</em> and <em>${result.flight?.operator || 'Selected Transit'}</em>.`;
        summaryTextEl.innerHTML = narrative;
    }
    
    // 2. Day-by-day Itinerary Timeline
    const timelineContainer = document.getElementById('itinerary-timeline');
    if (timelineContainer) {
        timelineContainer.innerHTML = '';
        const itineraryList = Array.isArray(result.itinerary) ? result.itinerary : [];
        
        itineraryList.forEach(day => {
            const block = document.createElement('div');
            block.className = 'day-block';
            
            block.innerHTML = `
                <div class="day-header">
                    <h3>Day ${day.day_number || ''}: ${day.date || ''}</h3>
                </div>
                <div class="activities-grid">
                    <div class="activity-card">
                        <span class="act-time"><i class="fa-regular fa-sun"></i> Morning Activity</span>
                        <h4>${day.morning?.activity || 'Morning Sightseeing'}</h4>
                        <div class="act-meta">
                            <span><i class="fa-regular fa-clock"></i> ${day.morning?.duration || '2h'}</span>
                            <span><i class="fa-solid fa-indian-rupee-sign"></i> ${day.morning?.cost === 0 ? 'Free' : (day.morning?.cost || 0) + ' INR'}</span>
                            <span><i class="fa-solid fa-map-location-dot"></i> ${day.morning?.location || ''}</span>
                        </div>
                    </div>
                    <div class="activity-card">
                        <span class="act-time"><i class="fa-solid fa-sun"></i> Afternoon Activity</span>
                        <h4>${day.afternoon?.activity || 'Afternoon Exploration'}</h4>
                        <div class="act-meta">
                            <span><i class="fa-regular fa-clock"></i> ${day.afternoon?.duration || '3h'}</span>
                            <span><i class="fa-solid fa-indian-rupee-sign"></i> ${day.afternoon?.cost === 0 ? 'Free' : (day.afternoon?.cost || 0) + ' INR'}</span>
                            <span><i class="fa-solid fa-map-location-dot"></i> ${day.afternoon?.location || ''}</span>
                        </div>
                    </div>
                    <div class="activity-card">
                        <span class="act-time"><i class="fa-solid fa-moon"></i> Evening & Dinner</span>
                        <h4>${day.evening?.activity || 'Evening Leisure'}</h4>
                        <div class="act-meta">
                            <span><i class="fa-solid fa-indian-rupee-sign"></i> ${day.evening?.cost === 0 ? 'Free' : (day.evening?.cost || 0) + ' INR'}</span>
                            <span><i class="fa-solid fa-map-location-dot"></i> ${day.evening?.location || ''}</span>
                        </div>
                    </div>
                </div>
                <div class="day-insights-card">
                    <div class="dining-rec">
                        <h5><i class="fa-solid fa-utensils"></i> Dining Recommendation</h5>
                        <p><strong>${day.restaurant_recommendation?.name || 'Local Bistro'}</strong> — ${day.restaurant_recommendation?.cuisine || 'Regional'} (${day.restaurant_recommendation?.price_range || 'Moderate'})</p>
                    </div>
                    <div class="backup-rec">
                        <h5><i class="fa-solid fa-cloud-showers-heavy"></i> Weather Backup</h5>
                        <p>${day.backup_activity || 'Indoor museum or cafe experience.'}</p>
                    </div>
                    <div class="tip-rec">
                        <h5><i class="fa-solid fa-lightbulb"></i> Day Tip</h5>
                        <p>${day.travel_tips || 'Carry water and keep camera ready.'}</p>
                    </div>
                </div>
            `;
            timelineContainer.appendChild(block);
        });
    }
    
    // 3. Flights & Hotels Logistics
    const hotel = result.hotel || {};
    const flight = result.flight || {};
    
    const setElemText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    
    setElemText('hotel-name', hotel.name || 'Selected Accommodation');
    setElemText('hotel-location', hotel.location || 'Central Location');
    setElemText('hotel-distance', hotel.distance_to_attractions || 'Nearby');
    setElemText('hotel-price-night', `INR ${(hotel.price_per_night || 0).toLocaleString('en-IN')}`);
    setElemText('hotel-total-cost', `INR ${(hotel.total_cost || 0).toLocaleString('en-IN')}`);
    setElemText('hotel-notes', hotel.notes || '');
    
    const starsContainer = document.getElementById('hotel-stars');
    if (starsContainer) {
        starsContainer.innerHTML = '';
        const starCount = hotel.stars || 3;
        for (let i = 0; i < starCount; i++) {
            starsContainer.innerHTML += '<i class="fa-solid fa-star"></i> ';
        }
    }
    
    const amenitiesContainer = document.getElementById('hotel-facilities');
    if (amenitiesContainer) {
        amenitiesContainer.innerHTML = '';
        const facilities = Array.isArray(hotel.facilities) ? hotel.facilities : ['Free Wi-Fi', 'Room Service'];
        facilities.forEach(fac => {
            const span = document.createElement('span');
            span.className = 'fac-tag';
            span.textContent = fac;
            amenitiesContainer.appendChild(span);
        });
    }
    
    setElemText('transport-preference', flight.operator || 'Express Carrier');
    setElemText('flight-carrier', flight.operator || 'Express Carrier');
    setElemText('flight-class', flight.class || 'Economy');
    setElemText('flight-duration', flight.duration || 'Direct');
    setElemText('flight-times', `${flight.departure_time || '08:00'} - ${flight.arrival_time || '12:00'}`);
    setElemText('flight-price-pax', `INR ${(flight.price_per_person || 0).toLocaleString('en-IN')}`);
    
    const flightTotal = (flight.price_per_person || 0) * parseInt(paxVal || 1);
    setElemText('flight-total-cost', `INR ${flightTotal.toLocaleString('en-IN')}`);
    setElemText('flight-notes', flight.notes || '');
    
    // 4. Budget Breakdown Tab & Charts
    setElemText('budget-total-text', `INR ${(result.total_cost || 0).toLocaleString('en-IN')}`);
    
    const budgetItemsContainer = document.getElementById('budget-items-list');
    if (budgetItemsContainer) {
        budgetItemsContainer.innerHTML = '';
        
        const budgetLabels = [];
        const budgetData = [];
        const colorPalette = ['#0ea5e9', '#10b981', '#f59e0b', '#06b6d4', '#6366f1', '#ec4899'];
        
        let colorIdx = 0;
        const allocations = result.budget_allocations || {};
        for (const [key, value] of Object.entries(allocations)) {
            budgetLabels.push(key);
            budgetData.push(value);
            
            const rowColor = colorPalette[colorIdx % colorPalette.length];
            const row = document.createElement('div');
            row.className = 'budget-row';
            row.innerHTML = `
                <div class="row-label-wrap">
                    <span class="color-indicator" style="background-color: ${rowColor}"></span>
                    <span class="row-lbl">${key}</span>
                </div>
                <span class="row-val">INR ${Number(value).toLocaleString('en-IN')}</span>
            `;
            budgetItemsContainer.appendChild(row);
            colorIdx++;
        }
        
        if (budgetChart) {
            budgetChart.destroy();
        }
        
        const canvasEl = document.getElementById('budgetChart');
        if (canvasEl) {
            const ctx = canvasEl.getContext('2d');
            budgetChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: budgetLabels,
                    datasets: [{
                        data: budgetData,
                        backgroundColor: colorPalette.slice(0, budgetLabels.length),
                        borderWidth: 1,
                        borderColor: '#1e293b'
                    }]
                },
                options: {
                    cutout: '75%',
                    plugins: { legend: { display: false } },
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
    }
    
    // 5. Local Insights Tab
    const fillList = (elementId, itemsArray) => {
        const ul = document.getElementById(elementId);
        if (!ul) return;
        ul.innerHTML = '';
        const list = Array.isArray(itemsArray) ? itemsArray : [];
        list.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            ul.appendChild(li);
        });
    };
    
    const insights = result.local_insights || {};
    fillList('insights-food', insights.must_try_food);
    fillList('insights-cultural', insights.cultural_tips);
    fillList('insights-safety', insights.safety_notes);
    fillList('insights-packing', insights.packing_list);
    
    // 6. Complete Report Content View (Directly Visible)
    const renderedEl = document.getElementById('rendered-report-view');
    if (renderedEl) {
        if (result.final_report) {
            if (window.marked && typeof window.marked.parse === 'function') {
                renderedEl.innerHTML = window.marked.parse(result.final_report);
            } else {
                renderedEl.innerHTML = `<div style="white-space: pre-wrap; font-family: inherit; line-height: 1.7;">${result.final_report}</div>`;
            }
        } else {
            renderedEl.innerHTML = `<p>Travel dossier is ready. Please view the day-by-day plan and logistics tabs.</p>`;
        }
    }
}

// 7. Download PDF Report (With Booking Confirmation & Itinerary)
downloadBtn.addEventListener('click', () => {
    if (!travelPlanResult) {
        alert("No travel plan available to export.");
        return;
    }
    
    const dest = travelPlanResult.destination || 'Destination';
    const safeDestName = dest.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const dateVal = travelPlanResult.travel_dates || 'Selected Dates';
    const paxVal = travelPlanResult.num_travellers || '1';
    const totalBudgetFormatted = travelPlanResult.total_cost ? Number(travelPlanResult.total_cost).toLocaleString('en-IN') : '0';
    
    // Create printable PDF container
    const pdfContainer = document.createElement('div');
    pdfContainer.id = 'pdf-export-container';
    pdfContainer.style.padding = '30px 35px';
    pdfContainer.style.backgroundColor = '#ffffff';
    pdfContainer.style.color = '#0f172a';
    pdfContainer.style.fontFamily = "'Plus Jakarta Sans', Arial, Helvetica, sans-serif";
    pdfContainer.style.fontSize = '12px';
    pdfContainer.style.lineHeight = '1.6';
    
    // Booking Confirmation Section in PDF
    let bookingSectionPdf = '';
    if (bookingConfirmationData) {
        const bc = bookingConfirmationData;
        const tb = bc.transport_booking || bc.flight_booking;
        const hb = bc.accommodation_booking;
        
        let transportBox = '';
        if (tb && tb.price > 0) {
            const mode = tb.mode || (tb.booking_id && tb.booking_id.startsWith('TRN') ? 'Train' : 
                         (tb.booking_id && tb.booking_id.startsWith('BUS') ? 'Bus' : 
                         (tb.booking_id && tb.booking_id.startsWith('CAB') ? 'Cab' : 
                         (tb.booking_id && tb.booking_id.startsWith('FLY') ? 'Flight' : 'Transport'))));
            const carrier = tb.operator || tb.airline || `${mode} Service`;
            const snum = tb.service_number || tb.flight_number || 'TR-101';
            
            transportBox = `
                <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; background: #fafafa;">
                    <strong style="color: #0284c7; font-size: 12px;">${mode} Confirmation: ${tb.booking_id}</strong>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Operator / Service:</strong> ${carrier} (${snum})</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Route:</strong> ${tb.from_location} → ${tb.to_location}</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Schedule:</strong> ${tb.departure_time} - ${tb.arrival_time} (${tb.departure_date})</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Status:</strong> ${tb.status} | Total Fare: INR ${Number(tb.price).toLocaleString('en-IN')}</p>
                </div>
            `;
        }
        
        let hotelBox = '';
        if (hb && hb.price > 0) {
            hotelBox = `
                <div style="flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; background: #fafafa;">
                    <strong style="color: #0284c7; font-size: 12px;">Accommodation Confirmation: ${hb.booking_id}</strong>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Hotel:</strong> ${hb.hotel_name}</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Location:</strong> ${hb.location}</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Dates:</strong> ${hb.check_in} to ${hb.check_out}</p>
                    <p style="margin: 3px 0; font-size: 11px;"><strong>Status:</strong> ${hb.status} | Total Lodging: INR ${Number(hb.price).toLocaleString('en-IN')}</p>
                </div>
            `;
        }
        
        const travellersStr = (bc.traveller_names || []).join(', ');
        
        bookingSectionPdf = `
            <div style="background-color: #f8fafc; border: 1.5px solid #0284c7; border-radius: 8px; padding: 14px 18px; margin-bottom: 22px; page-break-inside: avoid;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 10px;">
                    <h3 style="margin: 0; color: #0284c7; font-size: 14px; text-transform: uppercase;">Booking Confirmation (Mock Demonstration)</h3>
                    <span style="font-size: 11px; background: #ecfdf5; color: #059669; padding: 3px 8px; border-radius: 4px; font-weight: bold;">Demo Payment Successful</span>
                </div>
                <p style="margin: 0 0 8px 0; font-size: 11.5px; color: #334155;"><strong>Registered Travellers:</strong> ${travellersStr}</p>
                <div style="display: flex; gap: 12px; margin-top: 8px;">
                    ${transportBox}
                    ${hotelBox}
                </div>
            </div>
        `;
    }
    
    // Day-by-day Itinerary HTML
    let itineraryHtml = '';
    if (travelPlanResult.itinerary && Array.isArray(travelPlanResult.itinerary)) {
        itineraryHtml = travelPlanResult.itinerary.map(day => `
            <div style="margin-bottom: 16px; border-left: 3.5px solid #0284c7; padding-left: 14px; page-break-inside: avoid;">
                <h4 style="margin: 0 0 6px 0; color: #0f172a; font-size: 13.5px; font-weight: 700;">Day ${day.day_number}: ${day.date} <span style="font-size: 11px; font-weight: normal; color: #64748b;">(Estimated Day Cost: INR ${day.daily_total_cost ? Number(day.daily_total_cost).toLocaleString('en-IN') : 0})</span></h4>
                <div style="margin: 3px 0;"><strong style="color: #0369a1;">Morning:</strong> ${day.morning?.activity || 'Sightseeing'} <span style="color: #64748b; font-size: 11px;">(${day.morning?.location || ''} • ${day.morning?.cost === 0 ? 'Free' : 'INR ' + day.morning?.cost})</span></div>
                <div style="margin: 3px 0;"><strong style="color: #0369a1;">Afternoon:</strong> ${day.afternoon?.activity || 'Activities'} <span style="color: #64748b; font-size: 11px;">(${day.afternoon?.location || ''} • ${day.afternoon?.cost === 0 ? 'Free' : 'INR ' + day.afternoon?.cost})</span></div>
                <div style="margin: 3px 0;"><strong style="color: #0369a1;">Evening:</strong> ${day.evening?.activity || 'Dinner'} <span style="color: #64748b; font-size: 11px;">(${day.evening?.location || ''} • ${day.evening?.cost === 0 ? 'Free' : 'INR ' + day.evening?.cost})</span></div>
                <div style="margin: 4px 0; color: #334155;"><strong>Dining Spot:</strong> ${day.restaurant_recommendation?.name || 'Local Restaurant'} <em>(${day.restaurant_recommendation?.cuisine || ''} - ${day.restaurant_recommendation?.price_range || ''})</em></div>
            </div>
        `).join('');
    }
    
    // Budget Breakdown HTML
    let budgetRowsHtml = '';
    if (travelPlanResult.budget_allocations) {
        budgetRowsHtml = Object.entries(travelPlanResult.budget_allocations).map(([k, v]) => `
            <tr>
                <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">${k}</td>
                <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600; color: #0f172a;">INR ${Number(v).toLocaleString('en-IN')}</td>
            </tr>
        `).join('');
    }
    
    pdfContainer.innerHTML = `
        <div style="border-bottom: 2.5px solid #0284c7; padding-bottom: 14px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-end;">
            <div>
                <h1 style="margin: 0; color: #0284c7; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">SMART TRAVEL PLANNER</h1>
                <h2 style="margin: 4px 0 0 0; color: #0f172a; font-size: 17px; font-weight: 700;">Complete Trip Dossier: ${dest}</h2>
            </div>
            <div style="text-align: right; font-size: 11.5px; color: #475569;">
                <div><strong>Travel Dates:</strong> ${dateVal}</div>
                <div><strong>Group Size:</strong> ${paxVal} Pax</div>
                <div><strong>Total Estimated Budget:</strong> <span style="color: #0284c7; font-weight: 700;">INR ${totalBudgetFormatted}</span></div>
            </div>
        </div>
        
        ${bookingSectionPdf}
        
        <div style="background-color: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 14px 18px; margin-bottom: 22px;">
            <h3 style="margin: 0 0 6px 0; color: #0369a1; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Executive Trip Summary</h3>
            <p style="margin: 0; color: #334155; font-size: 12px; line-height: 1.55;">${travelPlanResult.rationale || `A curated journey to ${dest} optimized for ${paxVal} traveler(s) with an estimated total expenditure of INR ${totalBudgetFormatted}.`}</p>
        </div>
        
        <div style="margin-bottom: 22px;">
            <h3 style="margin: 0 0 12px 0; color: #0f172a; font-size: 15px; border-bottom: 1.5px solid #0284c7; padding-bottom: 4px;">Day-by-Day Itinerary</h3>
            ${itineraryHtml}
        </div>
        
        <div style="margin-bottom: 22px; page-break-inside: avoid;">
            <h3 style="margin: 0 0 10px 0; color: #0f172a; font-size: 14px; border-bottom: 1.5px solid #0284c7; padding-bottom: 4px;">Cost Breakdown</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 11.5px;">
                <tbody>
                    ${budgetRowsHtml}
                    <tr style="background: #f1f5f9; font-weight: bold;">
                        <td style="padding: 8px 10px; border-top: 2px solid #cbd5e1;">Grand Total</td>
                        <td style="padding: 8px 10px; border-top: 2px solid #cbd5e1; text-align: right; color: #0284c7;">INR ${totalBudgetFormatted}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; margin-top: 22px; text-align: center; font-size: 10.5px; color: #94a3b8;">
            Generated by SmartTravel AI Autonomous Flow Engine • Powered by Google Gemini & CrewAI • Demo/Mock System
        </div>
    `;
    
    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating PDF...';
    downloadBtn.disabled = true;
    
    if (window.html2pdf) {
        const opt = {
            margin: [10, 10, 10, 10],
            filename: `TravelPlan_${safeDestName}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true, letterRendering: true },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        };
        
        window.html2pdf().set(opt).from(pdfContainer).save()
            .then(() => {
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
            })
            .catch(err => {
                console.error("html2pdf failed:", err);
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
                const printWin = window.open('', '', 'width=850,height=950');
                printWin.document.write(`<html><head><title>Travel Plan - ${dest}</title></head><body>${pdfContainer.outerHTML}</body></html>`);
                printWin.document.close();
                printWin.focus();
                printWin.print();
            });
    } else {
        const printWin = window.open('', '', 'width=850,height=950');
        printWin.document.write(`<html><head><title>Travel Plan - ${dest}</title></head><body>${pdfContainer.outerHTML}</body></html>`);
        printWin.document.close();
        printWin.focus();
        printWin.print();
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = false;
    }
});
