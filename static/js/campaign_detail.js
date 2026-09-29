// static/js/campaign_detail.js
var campaignId = null;

function loadBackers() {
    fetch('/api/campaigns/campaigns/' + campaignId + '/contributors/')
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            var container = document.getElementById('backersList');
            container.innerHTML = '';
            
            if (data.results && data.results.length > 0) {
                for (var i = 0; i < data.results.length; i++) {
                    var backer = data.results[i];
                    var div = document.createElement('div');
                    div.className = 'backer-item';
                    var name = backer.is_anonymous ? 'Anonymous' : backer.user_name;
                    
                    var firstLetter = '?';
                    if (backer.user_name && backer.user_name.length > 0) {
                        firstLetter = backer.user_name.charAt(0).toUpperCase();
                    }
                    
                    div.innerHTML = '<div><span class="backer-avatar">' + firstLetter + '</span>' + name + '</div><div class="backer-amount">Ksh ' + formatNumber(backer.amount) + '</div>';
                    container.appendChild(div);
                }
            } else {
                container.innerHTML = '<p style="text-align: center; color: #718096;">No contributions yet. Be the first!</p>';
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            document.getElementById('backersList').innerHTML = '<p style="text-align: center; color: #718096;">Unable to load backers</p>';
        });
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

document.addEventListener('DOMContentLoaded', function() {
    var campaignDataElement = document.getElementById('campaign-data');
    if (campaignDataElement) {
        campaignId = campaignDataElement.getAttribute('data-campaign-id');
    }
    
    if (!campaignId) {
        console.error('Campaign ID not found');
        return;
    }
    
    loadBackers();
});