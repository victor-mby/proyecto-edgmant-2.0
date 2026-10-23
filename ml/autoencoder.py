import torch
import torch.nn as nn
import numpy as np


class Autoencoder(nn.Module):
    def __init__(self, input_dim, bottleneck_dim=8):
        if not isinstance(input_dim, int) or input_dim < 1:
            raise ValueError('input_dim debe ser un entero positivo.')
        if not isinstance(bottleneck_dim, int) or bottleneck_dim < 1:
            raise ValueError('bottleneck_dim debe ser un entero positivo.')
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, max(bottleneck_dim * 2, input_dim // 2)),
            nn.ReLU(),
            nn.Linear(max(bottleneck_dim * 2, input_dim // 2), bottleneck_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck_dim, max(bottleneck_dim * 2, input_dim // 2)),
            nn.ReLU(),
            nn.Linear(max(bottleneck_dim * 2, input_dim // 2), input_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)


def entrenar_autoencoder(X, epochs=50, batch_size=64, lr=1e-3, device=None):
    X = np.asarray(X, dtype=np.float32)
    if X.ndim != 2 or X.shape[0] == 0 or X.shape[1] == 0:
        raise ValueError('X debe ser una matriz 2D no vacía para entrenar el Autoencoder.')
    if not np.isfinite(X).all():
        raise ValueError('X contiene valores no finitos; limpia los datos antes de entrenar.')
    if not isinstance(epochs, int) or epochs < 1:
        raise ValueError('epochs debe ser un entero positivo.')
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError('batch_size debe ser un entero positivo.')
    if not np.isfinite(lr) or lr <= 0:
        raise ValueError('lr debe ser un número finito positivo.')

    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    X_tensor = torch.tensor(X, dtype=torch.float32)
    dataset = torch.utils.data.TensorDataset(X_tensor, X_tensor)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    input_dim = X.shape[1]
    bottleneck_dim = max(4, input_dim // 3)
    modelo = Autoencoder(input_dim, bottleneck_dim).to(device)
    criterio = nn.MSELoss()
    optimizador = torch.optim.Adam(modelo.parameters(), lr=lr)

    modelo.train()
    for epoch in range(epochs):
        perdida_total = 0.0
        for x_batch, _ in loader:
            x_batch = x_batch.to(device)
            reconstruido = modelo(x_batch)
            loss = criterio(reconstruido, x_batch)
            if not torch.isfinite(loss):
                raise ValueError('El entrenamiento produjo una pérdida no finita; revisa los datos y la tasa de aprendizaje.')
            optimizador.zero_grad()
            loss.backward()
            optimizador.step()
            perdida_total += loss.item() * x_batch.size(0)
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f'Epoch {epoch+1}/{epochs} - Loss: {perdida_total / len(X_tensor):.6f}')
    return modelo, device


def calcular_error_reconstruccion(modelo, X, device=None):
    X = np.asarray(X, dtype=np.float32)
    if X.ndim != 2 or X.shape[0] == 0:
        raise ValueError('La entrada para calcular errores debe ser una matriz no vacía.')
    if not np.isfinite(X).all():
        raise ValueError('La entrada para calcular errores contiene valores no finitos.')

    if device is None:
        device = next(modelo.parameters()).device
    modelo.eval()
    X_tensor = torch.as_tensor(X, dtype=torch.float32, device=device)
    with torch.no_grad():
        reconstruido = modelo(X_tensor).cpu().numpy()

    if not np.isfinite(reconstruido).all():
        raise ValueError('El Autoencoder produjo valores no finitos durante la reconstrucción.')

    errores = np.mean((X - reconstruido) ** 2, axis=1)
    if not np.isfinite(errores).all():
        raise ValueError('El error de reconstrucción contiene valores no finitos.')
    return errores, reconstruido
