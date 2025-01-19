document.addEventListener('DOMContentLoaded', () => {
    // Fetch API response when page loads
    fetch('/api/hello')
        .then(response => response.json())
        .then(data => {
            const apiResponseDiv = document.getElementById('api-response');
            if (apiResponseDiv) {
                apiResponseDiv.innerHTML = `
                    <h2>API Response:</h2>
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching API:', error);
        });

    const stripe = Stripe('{{ stripe_publishable_key }}');
    const checkoutButtons = document.querySelectorAll('.checkout-button');

    checkoutButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const plan = event.target.getAttribute('data-plan');

            try {
                const response = await fetch('/create-checkout-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `plan=${plan}`
                });

                const session = await response.json();

                if (session.error) {
                    console.error('Error creating checkout session:', session.error);
                    return;
                }

                // Redirect to Stripe Checkout
                const result = await stripe.redirectToCheckout({
                    sessionId: session.sessionId
                });

                if (result.error) {
                    console.error('Stripe Checkout error:', result.error);
                }
            } catch (error) {
                console.error('Checkout process error:', error);
            }
        });
    });
});
