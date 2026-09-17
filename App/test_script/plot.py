import os
import matplotlib.pyplot as plt
import numpy as np

output_dir = "comparison_plots"
os.makedirs(output_dir, exist_ok=True)

plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 12,
    'axes.labelsize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 11
})


authors_gal = ['This Work', 'van Albada et al.\n(1985)', 'Karukes et al.\n(2015)', 'Taga & Iye\n(1994)']
masses_tot_gal = np.array([2.05, 1.5, 8.9, 1.2])
dm_percent_gal = np.array([79.0, 80.0, 96.0, 75.0])

radii_labels_gal = ['R = 44.1 kpc', 'R = 30 kpc', 'R = Virial', 'R = 30 kpc']
colors_gal = ['crimson', 'royalblue', 'forestgreen', 'purple']
markers_gal = ['*', 'o', 's', 'D']


offsets = [(12, -5), (0, 15), (0, -18), (12, -5)]       
alignments = ['left', 'center', 'center', 'left']

fig_gal, ax_gal = plt.subplots(figsize=(8, 6))

for i in range(len(authors_gal)):

    ax_gal.scatter(masses_tot_gal[i], dm_percent_gal[i], color=colors_gal[i], marker=markers_gal[i],
                   s=100, label=authors_gal[i], zorder=5, edgecolor='black')
    
    ax_gal.annotate(radii_labels_gal[i], (masses_tot_gal[i], dm_percent_gal[i]),
                    xytext=offsets[i], textcoords='offset points', 
                    fontsize=11, ha=alignments[i], va='center')

ax_gal.set_xlabel(r'Total Mass ($10^{11} M_\odot$)')
ax_gal.set_ylabel('Dark Matter Fraction (%)')
ax_gal.set_xlim(0.5, 10.5)
ax_gal.set_ylim(65, 100)
ax_gal.grid(True, linestyle='--', alpha=0.6, zorder=0)
ax_gal.legend(loc='lower right', frameon=True, shadow=True)

plt.tight_layout()
#plt.savefig(os.path.join(output_dir, 'DM_vs_Mass_NGC3198_Final.pdf'), format='pdf', bbox_inches='tight')
plt.savefig(os.path.join(output_dir, 'DM_vs_Mass_NGC3198_Final.png'), dpi=300, bbox_inches='tight')
plt.close(fig_gal)



authors_mass = [
    'This Work', 
    'Kubo et al.\n(2007)', 
    'Gavazzi et al.\n(2009)', 
    'Okabe et al.\n(2014)', 
    'Lokas & Mamon\n(2003)'
]

mass_values = [1.64, 2.68, 1.11, 1.20, 1.40]

mass_errors = np.array([
    [0.0, 0.80, 0.61, 0.35, 0.40],  # Errori Inferiori
    [0.0, 0.93, 1.67, 0.60, 0.40]   # Errori Superiori
])

colors_mass = ['crimson', 'forestgreen', 'darkorange', 'purple', 'royalblue']
markers_mass = ['*', 's', '^', 'D', 'o']

authors_dm = ['This Work', 'Lokas & Mamon\n(2003)']
mass_dm = [1.64, 1.40]
dm_frac = [90.0, 85.0]
colors_dm = ['crimson', 'royalblue']
markers_dm = ['*', 'o']

fig_clus, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

y_pos_mass = np.arange(len(authors_mass))

# PLOT DI SINISTRA (Massa Totale)
for i in range(len(authors_mass)):
    ax1.errorbar(mass_values[i], y_pos_mass[i], 
                 xerr=[[mass_errors[0][i]], [mass_errors[1][i]]],
                 fmt=markers_mass[i], color=colors_mass[i], 
                 markersize=12, capsize=5, elinewidth=2, markeredgecolor='black')

ax1.set_yticks(y_pos_mass)
ax1.set_yticklabels(authors_mass)
ax1.invert_yaxis() 
ax1.set_xlabel(r'Total Mass ($10^{15} M_\odot$)')
ax1.grid(True, axis='x', linestyle='--', alpha=0.7)
ax1.axvline(x=1.64, color='crimson', linestyle=':', alpha=0.4) 


for i in range(len(authors_dm)):
   
    ax2.scatter(mass_dm[i], dm_frac[i], color=colors_dm[i], marker=markers_dm[i],
                s=250, label=authors_dm[i], edgecolor='black', zorder=5)
    
    
    if i == 1:
        ax2.errorbar(mass_dm[i], dm_frac[i], 
                     xerr=0.4, yerr=4.0, 
                     fmt='none', ecolor=colors_dm[i], 
                     capsize=5, elinewidth=2, zorder=4)

ax2.set_xlabel(r'Total Mass ($10^{15} M_\odot$)')
ax2.set_ylabel('Dark Matter Fraction (%)')
ax2.set_xlim(0.8, 4.0)
ax2.set_ylim(80, 100)
ax2.grid(True, linestyle='--', alpha=0.6)
ax2.legend(loc='lower right', framealpha=0.9, shadow=True)

plt.tight_layout()
#plt.savefig(os.path.join(output_dir, 'Coma_Comparison_Final.pdf'), format='pdf', bbox_inches='tight')
plt.savefig(os.path.join(output_dir, 'Coma_Comparison_Final.png'), dpi=300, bbox_inches='tight')
